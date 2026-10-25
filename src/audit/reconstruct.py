"""Build the single clean interaction table every later script reads.

Run from the repo root:
    uv run python src/audit/reconstruct.py

Steps, each reported with the number of interactions removed:
  1. Load both question-level files (train folds 0-4, test fold -1).
  2. Drop padded cells (selectmasks == -1; test has none).
  3. Concatenate each uid's rows in timestamp order.
  4. Batch dedup: within (uid, ts), keep the first occurrence of each
     (question, response) pair. See docs/exploration/..._same_batch.txt.
  5. Exclude students with any timestamp before 2019-01-01.
  6. Assign seq_pos (0-based position in the cleaned sequence), attempt
     number per (uid, question), and the previous attempt's response,
     timestamp and position.
Writes:
  data/processed/xes3g5m_clean.parquet   one row per interaction
  data/processed/reconstruct_log.json    counts for the paper's data section
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("data/raw/XES3G5M/question_level")
OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)
TS_CUTOFF_MS = int(pd.Timestamp("2019-01-01").value // 10**6)

log: dict[str, int | float | dict] = {}


def explode(df: pd.DataFrame, split: str) -> pd.DataFrame:
    cols = ["questions", "concepts", "responses", "timestamps"]
    parts = {c: df[c].str.split(",") for c in cols}
    has_mask = "selectmasks" in df.columns
    if has_mask:
        parts["selectmasks"] = df["selectmasks"].str.split(",")
    lens = parts["questions"].str.len()
    for c in parts:
        assert (lens == parts[c].str.len()).all(), f"{c} length mismatch"
    long = pd.DataFrame({
        "split": split,
        "fold": df["fold"].astype(int).repeat(lens).values,
        "uid": df["uid"].astype(int).repeat(lens).values,
        "row": np.repeat(np.arange(len(df)), lens),
        "pos_in_row": np.concatenate([np.arange(n) for n in lens]),
        "question": np.concatenate(parts["questions"].values).astype(int),
        "concepts": np.concatenate(parts["concepts"].values),
        "response": np.concatenate(parts["responses"].values).astype(int),
        "ts": np.concatenate(parts["timestamps"].values).astype(np.int64),
    })
    long["mask"] = (np.concatenate(parts["selectmasks"].values).astype(int) if has_mask else 1)
    return long


def step(name: str, before: int, after: int) -> None:
    log[name] = {"before": before, "after": after, "removed": before - after}
    print(f"{name:<32} {before:>10,} -> {after:>10,}   (removed {before - after:,})")


def main() -> None:
    # 1. load
    train = pd.read_csv(ROOT / "train_valid_sequences_quelevel.csv", dtype=str)
    test = pd.read_csv(ROOT / "test_quelevel.csv", dtype=str)
    long = pd.concat([explode(train, "train"), explode(test, "test")], ignore_index=True)
    n0 = len(long)
    log["raw_cells"] = n0
    print(f"raw cells (incl. padding)        {n0:>10,}")

    # 2. padding
    long = long[long["mask"] == 1].drop(columns="mask")
    step("drop padding", n0, len(long))

    # 3. order within uid
    long = long.sort_values(["uid", "ts", "row", "pos_in_row"], kind="stable").reset_index(drop=True)

    # 4. batch dedup: same (uid, ts, question) -> keep first occurrence
    n = len(long)
    diff_resp = (long.duplicated(subset=["uid", "ts", "question"], keep="first")
                 & ~long.duplicated(subset=["uid", "ts", "question", "response"], keep="first"))
    log["same_batch_repeats_with_different_response"] = int(diff_resp.sum())
    print(f"same-batch repeats with a different response (dropped, reported): {int(diff_resp.sum()):,}")
    long = long.drop_duplicates(subset=["uid", "ts", "question"], keep="first")
    step("batch dedup (uid,ts,q)", n, len(long))

    # 5. bad timestamps
    n = len(long)
    bad_uids = long.loc[long["ts"] < TS_CUTOFF_MS, "uid"].unique()
    long = long[~long["uid"].isin(bad_uids)]
    step(f"drop pre-2019 students ({len(bad_uids)})", n, len(long))
    log["excluded_uids_pre2019"] = [int(u) for u in bad_uids]

    # 6. positions and attempt bookkeeping
    long = long.reset_index(drop=True)
    long["seq_pos"] = long.groupby("uid").cumcount()
    g = long.groupby(["uid", "question"], sort=False)
    long["attempt"] = g.cumcount()
    long["prev_response"] = g["response"].shift()
    long["prev_ts"] = g["ts"].shift()
    long["prev_seq_pos"] = g["seq_pos"].shift()
    long["is_repeat"] = long["attempt"] >= 1
    # sanity: a repeat must now be in a strictly later batch
    rep = long[long["is_repeat"]]
    assert (rep["ts"] > rep["prev_ts"]).all(), "same-batch repeat survived dedup"
    long["gap_s"] = np.where(long["is_repeat"], (long["ts"] - long["prev_ts"]) / 1000, np.nan)
    long["gap_class"] = pd.cut(long["gap_s"], bins=[0, 3600, 86400, 7 * 86400, np.inf],
                               labels=["<1h", "<1d", "<7d", "7d+"], right=False)
    long["kind"] = np.where(long["is_repeat"],
                            np.where(long["prev_response"] == 0, "correction", "review"), None)
    long["n_kc"] = long["concepts"].str.count("_") + 1
    long["first_kc"] = long["concepts"].str.split("_").str[0].astype(int)

    # summary
    for split, d in long.groupby("split"):
        r = d[d["is_repeat"]]
        s = {
            "students": int(d["uid"].nunique()),
            "interactions": int(len(d)),
            "repeat_events": int(len(r)),
            "repeat_share": round(len(r) / len(d), 4),
            "students_with_repeat": int(r["uid"].nunique()),
            "students_with_repeat_share": round(r["uid"].nunique() / d["uid"].nunique(), 4),
            "corrections": int((r["kind"] == "correction").sum()),
            "reviews": int((r["kind"] == "review").sum()),
            "correction_success": round(r.loc[r["kind"] == "correction", "response"].mean(), 4),
            "review_retention": round(r.loc[r["kind"] == "review", "response"].mean(), 4),
            "gap_class_share": r["gap_class"].value_counts(normalize=True).round(4).to_dict(),
            "seq_len_median": int(d.groupby("uid").size().median()),
        }
        log[f"summary_{split}"] = s
        print(f"\n[{split}]")
        for k, v in s.items():
            print(f"  {k}: {v}")

    long.to_parquet(OUT / "xes3g5m_clean.parquet", index=False)
    with open(OUT / "reconstruct_log.json", "w") as f:
        json.dump(log, f, indent=2)
    print("\nwrote xes3g5m_clean.parquet and reconstruct_log.json")


if __name__ == "__main__":
    main()
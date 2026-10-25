"""What do selectmasks == -1 rows contain, and is per-uid reconstruction of train safe?

Run from the repo root:
    uv run python src/audit/check_mask.py

Answers, in order:
  1. Are all mask -1 cells pure padding (question == -1), or do some hold real ids?
  2. If real ids exist under mask -1, do they duplicate the tail of the uid's
     previous row ("used as history")?
  3. After filtering mask == 1 and concatenating by uid, is the sequence
     monotonic in time and free of exact duplicate interactions?
  4. Train repeat preview with padding removed (comparable to the test preview).
  5. Timestamp sanity: students with any stamp before 2019.
Writes data/processed/explore/train_clean_long.parquet for later scripts.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("data/raw/XES3G5M/question_level")
OUT = Path("data/processed/explore")
OUT.mkdir(parents=True, exist_ok=True)


def explode(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["questions", "concepts", "responses", "timestamps"]
    parts = {c: df[c].str.split(",") for c in cols}
    has_mask = "selectmasks" in df.columns
    if has_mask:
        parts["selectmasks"] = df["selectmasks"].str.split(",")
    lens = parts["questions"].str.len()
    long = pd.DataFrame({
        "uid": df["uid"].repeat(lens).values,
        "row": np.repeat(np.arange(len(df)), lens),
        "pos": np.concatenate([np.arange(n) for n in lens]),
        "question": np.concatenate(parts["questions"].values),
        "concepts": np.concatenate(parts["concepts"].values),
        "response": np.concatenate(parts["responses"].values).astype(int),
        "ts": np.concatenate(parts["timestamps"].values).astype(np.int64),
    })
    long["mask"] = np.concatenate(parts["selectmasks"].values).astype(int) if has_mask else 1
    return long


def mask_contents(long: pd.DataFrame) -> None:
    print("\n=== 1. What is under mask == -1? ===")
    m = long[long["mask"] == -1]
    print("mask -1 cells:", len(m))
    is_pad = m["question"] == "-1"
    print("  question == -1 (pure padding):", int(is_pad.sum()), f"({is_pad.mean():.2%})")
    print("  real question id:", int((~is_pad).sum()), f"({(~is_pad).mean():.2%})")
    if (~is_pad).any():
        real = m[~is_pad]
        print("  among real-id masked cells: response values", real["response"].value_counts().to_dict())
        print("  ts == -1 among them:", int((real["ts"] == -1).sum()))
    print("mask -1 response values:", m["response"].value_counts().to_dict())
    print("mask -1 ts == -1:", int((m["ts"] == -1).sum()), f"({(m['ts'] == -1).mean():.2%})")
    # Where does padding sit within a row? Should be a contiguous tail.
    pad_pos = m[is_pad].groupby("row")["pos"].agg(["min", "max", "count"])
    contiguous_tail = ((pad_pos["max"] - pad_pos["min"] + 1) == pad_pos["count"]) & (pad_pos["max"] == 199)
    print("rows with padding:", len(pad_pos), "| padding is a contiguous tail ending at pos 199:",
          f"{contiguous_tail.mean():.2%}")


def boundary_overlap(long: pd.DataFrame) -> None:
    """Does the start of a uid's row k repeat the end of row k-1?"""
    print("\n=== 2. Do consecutive rows of a uid overlap? ===")
    real = long[long["mask"] == 1].copy()
    # order rows within uid by first timestamp
    first_ts = real.groupby(["uid", "row"])["ts"].min().reset_index().sort_values(["uid", "ts"])
    first_ts["k"] = first_ts.groupby("uid").cumcount()
    real = real.merge(first_ts[["uid", "row", "k"]], on=["uid", "row"])
    sig = real.assign(sig=real["question"] + "|" + real["response"].astype(str) + "|" + real["ts"].astype(str))
    overlaps = []
    for uid, g in sig[sig["k"] >= 1].groupby("uid"):
        prev = sig[(sig["uid"] == uid) & (sig["k"] == 0)]
        prev_tail = set(prev.sort_values("pos")["sig"].tail(50))
        head = g[g["k"] == 1].sort_values("pos")["sig"].head(50)
        overlaps.append(int(head.isin(prev_tail).sum()))
        if len(overlaps) >= 2000:  # sample is enough to detect a systematic overlap
            break
    overlaps = np.array(overlaps)
    print("uids sampled:", len(overlaps))
    print("uids whose row-1 head repeats row-0 tail (>=1 identical interaction):",
          int((overlaps > 0).sum()), f"({(overlaps > 0).mean():.2%})")
    print("mean overlapping interactions when > 0:", round(overlaps[overlaps > 0].mean(), 1) if (overlaps > 0).any() else 0)


def reconstruct(long: pd.DataFrame) -> pd.DataFrame:
    print("\n=== 3. Reconstructed train sequences ===")
    real = long[long["mask"] == 1].sort_values(["uid", "ts", "row", "pos"]).copy()
    real["seq_pos"] = real.groupby("uid").cumcount()
    per_uid = real.groupby("uid").size()
    print("students:", len(per_uid), "| interactions:", len(real))
    print("interactions per student: min", per_uid.min(), "median", int(per_uid.median()),
          "mean", round(per_uid.mean(), 1), "max", per_uid.max())
    mono = real.groupby("uid")["ts"].apply(lambda s: bool((s.diff().dropna() >= 0).all()))
    print("monotonic ts within uid:", f"{mono.mean():.2%}")
    dup = real.duplicated(subset=["uid", "question", "response", "ts"], keep=False)
    print("exact duplicate (uid, question, response, ts) interactions:", int(dup.sum()),
          f"({dup.mean():.3%})  <- same-batch repeats with same answer will land here too")
    return real


def repeat_preview(real: pd.DataFrame) -> pd.DataFrame:
    print("\n=== 4. Train repeat preview (padding removed) ===")
    s = real.copy()
    s["attempt"] = s.groupby(["uid", "question"]).cumcount()
    s["prev_resp"] = s.groupby(["uid", "question"])["response"].shift()
    s["prev_ts"] = s.groupby(["uid", "question"])["ts"].shift()
    s["prev_row"] = s.groupby(["uid", "question"])["row"].shift()
    rep = s[s["attempt"] >= 1].copy()
    rep["gap_s"] = (rep["ts"] - rep["prev_ts"]) / 1000
    rep["gap_class"] = pd.cut(rep["gap_s"], bins=[-1, 0, 3600, 86400, 7 * 86400, np.inf],
                              labels=["same_batch", "<1h", "<1d", "<7d", "7d+"])
    rep["kind"] = np.where(rep["prev_resp"] == 0, "correction", "review")
    rep["crosses_row"] = rep["row"] != rep["prev_row"]
    n_uid = real["uid"].nunique()
    print("repeat events:", len(rep), f"({len(rep) / len(real):.2%} of interactions)")
    print("uids with >=1 repeat:", rep["uid"].nunique(), f"({rep['uid'].nunique() / n_uid:.1%})")
    print("by kind:\n", rep["kind"].value_counts().to_string())
    print("kind x gap:\n", pd.crosstab(rep["kind"], rep["gap_class"]).to_string())
    print("repeats crossing a row boundary:", int(rep["crosses_row"].sum()), f"({rep['crosses_row'].mean():.2%})")
    print("outcome on repeat | kind:\n", rep.groupby("kind")["response"].mean().round(3).to_string())
    print("attempt number distribution (1 = second attempt):\n",
          rep["attempt"].value_counts().sort_index().head(6).to_string())
    return rep


def timestamp_sanity(real: pd.DataFrame, label: str) -> None:
    print(f"\n=== 5. Timestamp sanity [{label}] ===")
    cutoff = pd.Timestamp("2019-01-01").value // 10**6  # ms
    bad = real[real["ts"] < cutoff]
    print("interactions before 2019:", len(bad), "| students affected:", bad["uid"].nunique())
    if len(bad):
        print("earliest:", pd.to_datetime(bad["ts"].min(), unit="ms").date(),
              "| example uids:", bad["uid"].unique()[:5].tolist())


def main() -> None:
    train = pd.read_csv(ROOT / "train_valid_sequences_quelevel.csv", dtype=str)
    long = explode(train)
    mask_contents(long)
    boundary_overlap(long)
    real = reconstruct(long)
    rep = repeat_preview(real)
    timestamp_sanity(real, "train")

    test = pd.read_csv(ROOT / "test_quelevel.csv", dtype=str)
    test_long = explode(test).sort_values(["uid", "ts", "pos"])
    timestamp_sanity(test_long, "test")

    real.to_parquet(OUT / "train_clean_long.parquet", index=False)
    rep.to_csv(OUT / "train_repeat_events_clean.csv", index=False)
    print("\nwrote:", "train_clean_long.parquet, train_repeat_events_clean.csv")


if __name__ == "__main__":
    main()
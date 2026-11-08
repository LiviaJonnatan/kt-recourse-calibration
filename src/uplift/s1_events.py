"""Stage 1 - clean interaction table and decision-event table for XES3G5M.

Reproduces the cleaning rules of kt-recourse-calibration/src/audit/reconstruct.py
(mask filter, same-batch dedup, pre-2019 exclusion, cross-batch repeats only) and
then builds the table every later stage reads: one row per interaction, labelled
as a decision event with the action the student actually took.

Action labels (what the student did at this position)
    new         first attempt at the question
    correction  re-attempt of a question previously answered wrong
    review      re-attempt of a question previously answered right
Outcome
    y_next      accuracy over the next N same-AREA interactions after this one,
                excluding later attempts at the same question (N = --window)
Covariates (dataset-agnostic by design, so the uplift model can transfer)
    gap_log     log10 seconds since the previous attempt at this question (0 for new)
    hist        number of prior interactions of the student
    pre_area    accuracy on the previous 10 same-area interactions (NaN if < 3)
    pre_all     accuracy on the previous 20 interactions overall
    n_area      prior interaction count in the area
    n_attempt   prior attempts at this question (0 for new)
    difficulty  1 - first-attempt accuracy of the question on train
    single      1 if single-choice question
    prev_resp   response at the previous attempt (NaN for new)

Usage
    python s1_events.py --raw ../../xes/XES3G5M --out ../out --window 5 --area_level 2
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

TS_CUTOFF_MS = int(pd.Timestamp("2019-01-01").value // 10**6)


def explode(df: pd.DataFrame, split: str) -> pd.DataFrame:
    cols = ["questions", "concepts", "responses", "timestamps"]
    parts = {c: df[c].str.split(",") for c in cols}
    has_mask = "selectmasks" in df.columns
    if has_mask:
        parts["selectmasks"] = df["selectmasks"].str.split(",")
    lens = parts["questions"].str.len()
    long = pd.DataFrame({
        "split": split,
        "fold": df["fold"].astype(int).repeat(lens).values,
        "uid": df["uid"].astype(int).repeat(lens).values,
        "question": np.concatenate(parts["questions"].values).astype(np.int32),
        "first_kc": [c.split("_")[0] for c in np.concatenate(parts["concepts"].values)],
        "response": np.concatenate(parts["responses"].values).astype(np.int8),
        "ts": np.concatenate(parts["timestamps"].values).astype(np.int64),
    })
    long["mask"] = (np.concatenate(parts["selectmasks"].values).astype(np.int8) if has_mask else 1)
    return long


def load_clean(raw: Path, log: dict) -> pd.DataFrame:
    tr = pd.read_csv(raw / "question_level/train_valid_sequences_quelevel.csv")
    te = pd.read_csv(raw / "question_level/test_quelevel.csv")
    d = pd.concat([explode(tr, "train"), explode(te, "test")], ignore_index=True)
    log["raw_cells"] = len(d)
    d = d[d["mask"] == 1].drop(columns="mask")
    log["after_mask"] = len(d)
    d = d.sort_values(["uid", "ts"], kind="stable").reset_index(drop=True)
    d = d.drop_duplicates(["uid", "ts", "question", "response"], keep="first")
    d = d.drop_duplicates(["uid", "ts", "question"], keep="first")   # same-batch, different answer: drop too
    log["after_batch_dedup"] = len(d)
    bad = d.loc[d["ts"] < TS_CUTOFF_MS, "uid"].unique()
    d = d[~d["uid"].isin(bad)].reset_index(drop=True)
    log["after_pre2019"] = len(d)
    d["first_kc"] = d["first_kc"].astype(np.int32)
    d["seq_pos"] = d.groupby("uid").cumcount().astype(np.int32)
    g = d.groupby(["uid", "question"], sort=False)
    d["n_attempt"] = g.cumcount().astype(np.int16)
    d["prev_resp"] = g["response"].shift(1)
    d["prev_ts"] = g["ts"].shift(1)
    d["action"] = np.select(
        [d["n_attempt"] == 0, d["prev_resp"] == 0, d["prev_resp"] == 1],
        ["new", "correction", "review"], default="new")
    return d


def area_map(raw: Path, level: int) -> tuple[dict, dict]:
    q = json.load(open(raw / "metadata/questions.json", encoding="utf-8-sig"))
    area, single = {}, {}
    for qid, rec in q.items():
        routes = rec.get("kc_routes") or [""]
        parts = routes[0].split("----")
        area[int(qid)] = "----".join(parts[:level])
        single[int(qid)] = int(rec.get("type") == "单选")
    return area, single


def rolling_prev_acc(d: pd.DataFrame, keys: list[str], w: int, minn: int, name: str) -> None:
    """Accuracy over the previous w rows within keys (strictly before the row)."""
    g = d.groupby(keys, sort=False)
    c = g["response"].cumsum() - d["response"]
    n = g.cumcount()
    c_w = c.groupby([d[k] for k in keys]).shift(w)
    n_prev = (n - w).clip(lower=0)
    cnt = n - n_prev
    corr = c - c_w.fillna(0)
    d[name] = np.where(cnt >= minn, corr / cnt.replace(0, np.nan), np.nan)


def next_area_acc(d: pd.DataFrame, window: int) -> np.ndarray:
    """Accuracy on the next `window` same-area interactions after each row,
    excluding later attempts at the same question. NaN if fewer than `window`."""
    out = np.full(len(d), np.nan, dtype=np.float32)
    d = d.sort_values(["uid", "area", "seq_pos"])
    for _, g in d.groupby(["uid", "area"], sort=False):
        idx = g.index.to_numpy()
        qq = g["question"].to_numpy()
        rr = g["response"].to_numpy().astype(np.float32)
        n = len(g)
        if n <= window:
            continue
        for i in range(n - 1):
            keep = qq[i + 1:] != qq[i]
            r = rr[i + 1:][keep]
            if len(r) >= window:
                out[idx[i]] = r[:window].mean()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--window", type=int, default=5)
    ap.add_argument("--area_level", type=int, default=2)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    log: dict = {}

    d = load_clean(a.raw, log)
    area, single = area_map(a.raw, a.area_level)
    d["area"] = d["question"].map(area).astype("category")
    d["single"] = d["question"].map(single).astype(np.int8)

    # difficulty from TRAIN first attempts only (>= 30 attempts)
    fa = d[(d["split"] == "train") & (d["n_attempt"] == 0)].groupby("question")["response"].agg(["mean", "size"])
    diff = (1 - fa["mean"]).where(fa["size"] >= 30)
    d["difficulty"] = d["question"].map(diff).astype(np.float32)

    d = d.sort_values(["uid", "seq_pos"]).reset_index(drop=True)
    d["hist"] = d["seq_pos"]
    rolling_prev_acc(d, ["uid"], 20, 5, "pre_all")
    rolling_prev_acc(d, ["uid", "area"], 10, 3, "pre_area")
    d["n_area"] = d.groupby(["uid", "area"], sort=False).cumcount().astype(np.int32)
    gap_s = (d["ts"] - d["prev_ts"]) / 1000.0
    d["gap_log"] = np.where(d["n_attempt"] > 0, np.log10(gap_s.clip(lower=1)), 0.0).astype(np.float32)
    d["y_next"] = next_area_acc(d, a.window)

    log["events_total"] = len(d)
    log["events_with_outcome"] = int(d["y_next"].notna().sum())
    log["action_counts"] = d["action"].value_counts().to_dict()
    log["repeat_share"] = float((d["action"] != "new").mean())
    log["area_level"] = a.area_level
    log["n_areas"] = int(d["area"].nunique())
    log["window"] = a.window

    keep = ["split", "fold", "uid", "seq_pos", "question", "first_kc", "area", "response", "ts",
            "action", "n_attempt", "prev_resp", "gap_log", "hist", "pre_all", "pre_area", "n_area",
            "difficulty", "single", "y_next"]
    d[keep].to_parquet(a.out / "events.parquet", index=False)
    json.dump(log, open(a.out / "s1_log.json", "w"), indent=2)
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()

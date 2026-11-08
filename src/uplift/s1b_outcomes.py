"""Stage 1b - add alternative outcomes to an existing events.parquet (SLAM or XES3G5M).

    y_item     correctness at the learner's NEXT encounter of this same question/token
               (item-level recall; NaN if never seen again)
    lag_next   log10 seconds until that next encounter (post-treatment: diagnostics only,
               never a model input)
    y_area20   accuracy over the next 20 same-area interactions in later exercises
               (long window; falls back to seq_pos when no exercise_id column)

Usage: python s1b_outcomes.py --out ../out_slam
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def next_area_acc_later(d: pd.DataFrame, window: int) -> np.ndarray:
    out = np.full(len(d), np.nan, dtype=np.float32)
    has_ex = "exercise_id" in d.columns
    for _, g in d.groupby(["uid", "area"], sort=False, observed=True):
        idx = g.index.to_numpy(); qq = g["question"].to_numpy()
        ex = g["exercise_id"].to_numpy() if has_ex else g["seq_pos"].to_numpy()
        rr = g["response"].to_numpy().astype(np.float32); n = len(g)
        if n <= window:
            continue
        for i in range(n - 1):
            keep = (qq[i + 1:] != qq[i]) & (ex[i + 1:] != ex[i])
            r = rr[i + 1:][keep]
            if len(r) >= window:
                out[idx[i]] = r[:window].mean()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--long_window", type=int, default=20)
    a = ap.parse_args()
    d = pd.read_parquet(a.out / "events.parquet")
    d = d.sort_values(["uid", "seq_pos"]).reset_index(drop=True)
    g = d.groupby(["uid", "question"], sort=False)
    d["y_item"] = g["response"].shift(-1).astype("float32")
    nxt_ts = g["ts"].shift(-1)
    d["lag_next"] = np.log10(((nxt_ts - d["ts"]) / 1000.0).clip(lower=1)).astype("float32")
    d["y_area20"] = next_area_acc_later(d, a.long_window)
    d.to_parquet(a.out / "events.parquet", index=False)
    print({"rows": len(d), "y_item_defined": int(d["y_item"].notna().sum()),
           "y_item_rate": float(d["y_item"].mean()), "y_area20_defined": int(d["y_area20"].notna().sum()),
           "y_item_by_action": d.groupby("action")["y_item"].mean().round(3).to_dict()})


if __name__ == "__main__":
    main()

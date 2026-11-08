"""Rec 3 - review timing. The item-outcome uplift model has gap_log as a treated-arm
input, so tau(x, gap) is a curve per candidate. For every held-out re-attempt we compute
the model-optimal gap (argmax over a grid) and how far the ACTUAL gap was from it, then
check whether re-attempts that happened near the optimal time were followed by higher
next-recall than those far from it, relative to the control expectation mu0(x).
Compared with the half-life-regression rule (review when predicted recall ~ 0.5).

Outputs s6_timing_<arm>.csv: observed gain (y_item - mu0, and IPW vs controls) by |actual - optimal| bin,
plus the same by HLR predicted-recall bin.
"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

import s3_uplift
from s3_uplift import Uplift  # noqa: F401

if "p_hlr" not in s3_uplift.TREATED_EXTRA:
    s3_uplift.TREATED_EXTRA.append("p_hlr")

GRID = np.arange(1.0, 6.6, 0.25)          # log10 seconds: 10 s ... ~1.5 weeks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tag", default="_item")
    ap.add_argument("--n", type=int, default=60000)
    ap.add_argument("--arms", default="correction,review")
    a = ap.parse_args()
    for arm in a.arms.split(","):
        up = pickle.load(open(a.out / f"uplift_{arm}{a.tag}.pkl", "rb"))
        d = pd.read_parquet(a.out / f"scored_test_{arm}{a.tag}.parquet")
        tr = d[d["action"] == arm].sample(min(a.n, (d["action"] == arm).sum()), random_state=0).reset_index(drop=True)
        # tau over the gap grid, holding everything else fixed; p_hlr re-derived for each gap
        theta = np.array(__import__("json").load(open(a.out / "hlr_theta.json"))["theta"])
        xh = np.stack([np.ones(len(tr)), np.sqrt(1 + tr["seen"]), np.sqrt(1 + tr["correct"]), np.sqrt(1 + tr["wrong"])], 1)
        h = 2.0 ** (xh @ theta)
        taus = np.zeros((len(tr), len(GRID)), np.float32)
        for j, gl in enumerate(GRID):
            x = tr.copy(); x["gap_log"] = gl; x["p_hlr"] = 2.0 ** (-(10 ** gl / 86400) / h)
            taus[:, j] = up.score(x)["tau_t"].to_numpy()
        opt = GRID[taus.argmax(1)]
        tr["gap_opt"] = opt; tr["dist"] = np.abs(tr["gap_log"] - opt)
        tr["tau_at_opt"] = taus.max(1); tr["tau_at_actual"] = tr["tau_t"]
        tr["gain_vs_mu0"] = tr["y_next"] - tr["mu0"]
        bins = pd.cut(tr["dist"], [0, 0.5, 1.0, 2.0, 10], labels=["<0.5", "0.5-1", "1-2", ">2"], include_lowest=True)
        by_dist = tr.groupby(bins, observed=True).agg(n=("y_next", "size"), obs_recall=("y_next", "mean"), mu0=("mu0", "mean"),
                                                      gain_vs_mu0=("gain_vs_mu0", "mean"), tau_actual=("tau_at_actual", "mean"),
                                                      tau_opt=("tau_at_opt", "mean"), actual_gap=("gap_log", "mean"), opt_gap=("gap_opt", "mean"))
        hbins = pd.cut(tr["p_hlr"], [0, 0.5, 0.8, 0.95, 1.0], labels=["<0.5", "0.5-0.8", "0.8-0.95", ">0.95"], include_lowest=True)
        by_hlr = tr.groupby(hbins, observed=True).agg(n=("y_next", "size"), obs_recall=("y_next", "mean"), mu0=("mu0", "mean"),
                                                      gain_vs_mu0=("gain_vs_mu0", "mean"))
        print(f"\n== {arm}: gain in next recall vs control expectation, by distance of actual gap from model-optimal gap (log10 s)")
        print(by_dist.round(3).to_string())
        print(f"-- {arm}: same, by HLR predicted recall at the time of the re-attempt (the spaced-repetition rule)")
        print(by_hlr.round(3).to_string())
        print(f"-- {arm}: optimal gap distribution (log10 s): median {np.median(opt):.2f} = {10**np.median(opt)/3600:.1f} h; "
              f"share of re-attempts within 0.5 of optimal: {(tr['dist'] < 0.5).mean():.2f}")
        by_dist.to_csv(a.out / f"s6_timing_{arm}_by_dist.csv"); by_hlr.to_csv(a.out / f"s6_timing_{arm}_by_hlr.csv")


if __name__ == "__main__":
    main()

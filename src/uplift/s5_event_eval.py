"""Stage 5a - does the ranking signal know WHICH re-attempts help?

Held-out test events of arm a (treated) and new-question events in the same areas
(control), each with its observed next-5 outcome. Every ranker scores every event;
the Qini curve walks the ranking and accumulates observed treated-minus-control gain.
No simulator, no unobserved counterfactuals.

Rankers
    random                      floor
    p_dkt                       DKT predicted P(correct) on the event's KC  (predicted-correctness ranker, KTCF's signal)
    mu1                         predicted outcome AFTER the action (success-likelihood ranker)
    neg_difficulty              easiest first
    neg_gap                     most recent first (spacing heuristic, treated only -> ties for controls)
    tau_t / tau_x / tau_dr      uplift learners (ours)
    tau_lcb                     tau_t - z * sd  (pessimistic, ours)

Also: uplift calibration by decile of tau_dr (observed gain vs predicted), and an
IPW-weighted Qini using the propensity model (debiased curve).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from metrics import four_groups, ipw_weights, qini_coefficient, qini_curve, uplift_at_k

ARMS = ["correction", "review"]


def rankers(d: pd.DataFrame, rng, z: float = 1.0) -> dict[str, np.ndarray]:
    return {
        "random": rng.random(len(d)),
        "p_dkt": d["p_dkt"].to_numpy(),
        "mu1": d["mu1"].to_numpy(),
        "neg_difficulty": -d["difficulty"].to_numpy(),
        "neg_gap": -d["gap_log"].to_numpy(),
        "tau_t": d["tau_t"].to_numpy(),
        "tau_x": d["tau_x"].to_numpy(),
        "tau_dr": d["tau_dr"].to_numpy(),
        "tau_lcb": (d["tau_t"] - z * d["tau_sd"]).to_numpy(),
        **({"neg_p_hlr": -d["p_hlr"].fillna(1.0).to_numpy()} if "p_hlr" in d.columns else {}),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ctrl_per_treated", type=int, default=5, help="controls sampled per treated, within area")
    ap.add_argument("--tag", default="", help="suffix of scored_test files / outputs")
    ap.add_argument("--headroom", type=float, default=None, help="keep events with pre_area < this (room to improve)")
    a = ap.parse_args()
    rng = np.random.default_rng(7)
    rows, curves, calib, groups = [], {}, [], {}
    for arm in ARMS:
        d = pd.read_parquet(a.out / f"scored_test_{arm}{a.tag}.parquet")
        if a.headroom is not None:
            d = d[d["pre_area"] < a.headroom]
        tr = d[d["action"] == arm]
        # balanced control pool: sample controls within each area proportional to treated count
        ctrl = d[d["action"] == "new"]
        need = (tr["area"].value_counts() * a.ctrl_per_treated)
        ctrl = pd.concat([g.sample(min(len(g), int(need.get(k, 0))), random_state=1) for k, g in ctrl.groupby("area") if need.get(k, 0) > 0])
        e = pd.concat([tr, ctrl]).reset_index(drop=True)
        y = e["y_next"].to_numpy(np.float64); t = (e["action"] == arm).to_numpy(int)
        w = ipw_weights(t, e["e"].to_numpy())
        for name, s in rankers(e, rng).items():
            q = qini_coefficient(y, t, s)
            qw = qini_coefficient(y, t, s, w)
            rows.append({"arm": arm, "ranker": name, "qini": q["qini"], "qini_norm": q["qini_norm"],
                         "qini_ipw": qw["qini"], "qini_norm_ipw": qw["qini_norm"],
                         "uplift_top20": uplift_at_k(y, t, s, frac=0.2), "uplift_top20_ipw": uplift_at_k(y, t, s, w, 0.2),
                         "n_treated": int(t.sum()), "n_control": int((1 - t).sum())})
            if name in ("random", "p_dkt", "mu1", "tau_dr", "tau_lcb"):
                phi, g = qini_curve(y, t, s, n_points=41)
                curves[f"{arm}:{name}"] = {"phi": phi.tolist(), "g": g.tolist()}
        # calibration of tau_dr: observed gain per decile
        dec = pd.qcut(e["tau_dr"], 10, labels=False, duplicates="drop")
        for k, g in e.groupby(dec):
            tt = (g["action"] == arm).to_numpy(int); yy = g["y_next"].to_numpy()
            if tt.sum() > 20 and (1 - tt).sum() > 20:
                calib.append({"arm": arm, "decile": int(k), "pred_tau": float(g["tau_dr"].mean()),
                              "obs_gain": float(yy[tt == 1].mean() - yy[tt == 0].mean()), "n_treated": int(tt.sum())})
        groups[arm] = four_groups(tr["mu0"].to_numpy(), tr["mu1"].to_numpy()).to_dict()
        print(arm, "ATE naive on test:", round(float(y[t == 1].mean() - y[t == 0].mean()), 4),
              "ATE IPW:", round(float((w * t * y).sum() / (w * t).sum() - (w * (1 - t) * y).sum() / (w * (1 - t)).sum()), 4))
    res = pd.DataFrame(rows)
    hr = f"_hr{a.headroom}" if a.headroom is not None else ""
    res.to_csv(a.out / f"s5_event_qini{a.tag}{hr}.csv", index=False)
    pd.DataFrame(calib).to_csv(a.out / f"s5_tau_calibration{a.tag}{hr}.csv", index=False)
    json.dump({"curves": curves, "four_groups": groups}, open(a.out / f"s5_event_curves{a.tag}{hr}.json", "w"))
    pd.set_option("display.width", 200)
    print(res.round(4).to_string(index=False))
    print(pd.DataFrame(calib).round(4).to_string(index=False))
    print(json.dumps(groups, indent=1))


if __name__ == "__main__":
    main()

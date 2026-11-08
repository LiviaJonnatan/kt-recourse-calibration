"""Rec 5 - 'new practice' as a third action. At a decision point the choice is
re-attempt (correction/review of a past item) or a new item in the same area. The uplift
model already estimates tau = E[y | re-attempt] - E[y | new]; a policy that sends the
learner to NEW PRACTICE whenever tau_lcb <= 0 and to the re-attempt otherwise is
evaluated on held-out events by IPW: observed outcome under 'always re-attempt' vs under
the policy (for events where the policy says 'new', the control expectation is used,
estimated by IPW from matched new-item events in the same area).
"""
import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd
from metrics import ipw_weights

ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, required=True); ap.add_argument("--tag", default="")
ap.add_argument("--score", default="tau_lcb"); a = ap.parse_args()
rows = []
for arm in ["correction", "review"]:
    d = pd.read_parquet(a.out / f"scored_test_{arm}{a.tag}.parquet")
    d["tau_lcb"] = d["tau_t"] - d["tau_sd"]
    tr = d[d["action"] == arm]; ct = d[d["action"] == "new"]
    # control expectation per area (IPW-weighted mean of new-item outcomes)
    w_ct = 1 / np.clip(1 - ct["e"].to_numpy(), 0.01, 0.99)
    ctrl_area = (ct.assign(w=w_ct).groupby("area").apply(lambda g: np.average(g["y_next"], weights=g["w"]))).to_dict()
    tr = tr.assign(y_ctrl=tr["area"].map(ctrl_area)).dropna(subset=["y_ctrl"])
    w_tr = 1 / np.clip(tr["e"].to_numpy(), 0.01, 0.99)
    rec_new = tr[a.score].to_numpy() <= 0
    y_obs = tr["y_next"].to_numpy(); y_ct = tr["y_ctrl"].to_numpy()
    always = np.average(y_obs, weights=w_tr)
    policy = np.average(np.where(rec_new, y_ct, y_obs), weights=w_tr)
    for grp, m in [("policy says re-attempt", ~rec_new), ("policy says new practice", rec_new)]:
        rows.append({"arm": arm, "group": grp, "share": float(m.mean()), "n": int(m.sum()),
                     "obs_reattempt": float(np.average(y_obs[m], weights=w_tr[m])),
                     "ctrl_new_practice": float(np.average(y_ct[m], weights=w_tr[m])),
                     "diff_reattempt_minus_new": float(np.average(y_obs[m] - y_ct[m], weights=w_tr[m]))})
    rows.append({"arm": arm, "group": "VALUE: always re-attempt", "obs_reattempt": always})
    rows.append({"arm": arm, "group": "VALUE: policy (re-attempt or new)", "obs_reattempt": policy,
                 "diff_reattempt_minus_new": policy - always})
r = pd.DataFrame(rows); pd.set_option("display.width", 200); print(r.round(3).to_string(index=False))
r.to_csv(a.out / f"s7_new_practice{a.tag}.csv", index=False)

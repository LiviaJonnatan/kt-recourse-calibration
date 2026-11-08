"""#4 Student-clustered bootstrap CI for the gap between rankers' top-20% observed gains
(tau_LCB minus predicted correctness; tau_LCB minus random) on the same held-out events.

Usage (from src/uplift/):
    python s10_paired.py --out ../../out/slam --tag _s0 --B 300
Writes <out>/s10_paired<tag>.csv.
"""
import argparse
from pathlib import Path
import numpy as np, pandas as pd
from metrics import uplift_at_k

ap = argparse.ArgumentParser()
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--tag", default="")
ap.add_argument("--B", type=int, default=300)
a = ap.parse_args()
rng = np.random.default_rng(0); rows = []
for arm in ["correction", "review"]:
    d = pd.read_parquet(a.out / f"scored_test_{arm}{a.tag}.parquet")
    tr = d[d.action == arm]; ct = d[d.action == "new"]
    need = tr["area"].value_counts() * 5
    ct = pd.concat([g.sample(min(len(g), int(need.get(k, 0))), random_state=1)
                    for k, g in ct.groupby("area") if need.get(k, 0) > 0])
    e = pd.concat([tr, ct]).reset_index(drop=True)
    e["lcb"] = e["tau_t"] - e["tau_sd"]; e["rnd"] = rng.random(len(e))
    y = e["y_next"].to_numpy(float); t = (e.action == arm).to_numpy(int)
    uids = e["uid"].to_numpy(); uu = np.unique(uids)
    idx_by_u = pd.Series(np.arange(len(e))).groupby(uids).apply(np.array).to_dict()
    S = {k: e[k].to_numpy() for k in ["lcb", "p_dkt", "rnd"]}

    def gaps(ix):
        g = {k: uplift_at_k(y[ix], t[ix], S[k][ix], frac=.2) for k in S}
        return g["lcb"] - g["p_dkt"], g["lcb"] - g["rnd"]

    point = gaps(np.arange(len(e)))
    bs = np.array([gaps(np.concatenate([idx_by_u[u] for u in rng.choice(uu, len(uu), replace=True)])) for _ in range(a.B)])
    rows.append({"arm": arm, "n_students": len(uu), "n_treated": int(t.sum()),
                 "gap_vs_pcorrect": point[0], "ci_lo": np.percentile(bs[:, 0], 2.5), "ci_hi": np.percentile(bs[:, 0], 97.5),
                 "gap_vs_random": point[1], "ci_lo_r": np.percentile(bs[:, 1], 2.5), "ci_hi_r": np.percentile(bs[:, 1], 97.5)})
r = pd.DataFrame(rows)
pd.set_option("display.width", 200); print(r.round(3).to_string(index=False))
r.to_csv(a.out / f"s10_paired{a.tag}.csv", index=False)
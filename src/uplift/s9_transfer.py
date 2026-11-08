"""#5 Zero-shot transfer between SLAM and ASSISTments.

Scores dataset B's held-out events with the uplift model fitted on dataset A, and compares the
top-20% observed gain with B's own in-domain model, predicted correctness, and random.

Usage (from src/uplift/):
    python s9_transfer.py --out ../../out --tag _s0          # area outcome, seed 0
    python s9_transfer.py --out ../../out --tag _item_s0     # item outcome, seed 0
Expects out/slam and out/assist to hold uplift_{arm}<tag>.pkl and scored_test_{arm}<tag>.parquet.
Writes out/s9_transfer<tag>.csv.
"""
import argparse, pickle
from pathlib import Path
import numpy as np, pandas as pd
import s3_uplift
from s3_uplift import Uplift  # noqa: F401
from metrics import uplift_at_k

if "p_hlr" not in s3_uplift.TREATED_EXTRA:
    s3_uplift.TREATED_EXTRA.append("p_hlr")

ap = argparse.ArgumentParser()
ap.add_argument("--out", type=Path, required=True, help="root out/ dir containing slam/ and assist/")
ap.add_argument("--tag", default="")
a = ap.parse_args()
sets = {"slam": a.out / "slam", "assist": a.out / "assist"}
rows = []
for arm in ["correction", "review"]:
    for src, sdir in sets.items():
        up = pickle.load(open(sdir / f"uplift_{arm}{a.tag}.pkl", "rb"))
        for dst, ddir in sets.items():
            d = pd.read_parquet(ddir / f"scored_test_{arm}{a.tag}.parquet")
            tr = d[d.action == arm]; ct = d[d.action == "new"]
            need = tr["area"].value_counts() * 5
            ct = pd.concat([g.sample(min(len(g), int(need.get(k, 0))), random_state=1)
                            for k, g in ct.groupby("area") if need.get(k, 0) > 0])
            e = pd.concat([tr, ct]).reset_index(drop=True)
            for c in s3_uplift.TREATED_EXTRA:
                e[c] = e[c].fillna(0.0)
            sc = up.score(e)
            y = e["y_next"].to_numpy(float); t = (e.action == arm).to_numpy(int)
            rows.append({"arm": arm, "model_from": src, "evaluated_on": dst, "n_treated": int(t.sum()),
                         "tau_t": uplift_at_k(y, t, sc["tau_t"].to_numpy(), frac=.2),
                         "tau_lcb": uplift_at_k(y, t, (sc["tau_t"] - sc["tau_sd"]).to_numpy(), frac=.2),
                         "p_dkt": uplift_at_k(y, t, e["p_dkt"].to_numpy(), frac=.2),
                         "random": uplift_at_k(y, t, np.random.default_rng(0).random(len(e)), frac=.2)})
r = pd.DataFrame(rows)
pd.set_option("display.width", 200); print(r.round(3).to_string(index=False))
r.to_csv(a.out / f"s9_transfer{a.tag}.csv", index=False)
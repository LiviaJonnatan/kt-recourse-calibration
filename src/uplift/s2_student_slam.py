"""Stage 2 (SLAM) - student model. The sandbox has no PyTorch, so instead of a DKT we
fit a gradient-boosted classifier on the learner's running history (the shared task's
own baseline was logistic regression at 0.774 AUROC). It plays the same role DKT plays
on XES3G5M: P(correct) for every row, used as a covariate by stage 3 and as the
"predicted-correctness" ranking signal by stages 4-5. Replace with pyKT DKT on a GPU
by writing the same p_dkt_{split}.parquet files.

Also relabels dev -> test (both are held out; dev is each learner's middle 10%, test the
final 10%) so stages 3-5 see one evaluation split. Original split kept in split_orig.
Cross-fit by learner (2 folds) so train-split predictions are out-of-fold.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

FEATS = ["pre_all", "pre_area", "hist", "n_area", "difficulty", "seen", "correct", "wrong", "gap_log", "p_hlr",
         "single", "sess_practice", "sess_test", "fmt_listen", "fmt_rt", "rt"]


def featurise(d: pd.DataFrame) -> np.ndarray:
    x = d.copy()
    x["sess_practice"] = (x["session"] == "practice").astype(int)
    x["sess_test"] = (x["session"] == "test").astype(int)
    x["fmt_listen"] = (x["format"] == "listen").astype(int)
    x["fmt_rt"] = (x["format"] == "reverse_translate").astype(int)
    return x[FEATS].to_numpy(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    d = pd.read_parquet(a.out / "events.parquet")
    if "split_orig" not in d.columns:
        d["split_orig"] = d["split"]
        d["split"] = d["split"].replace({"dev": "test"})
        d["rt"] = d["rt"].astype(float) if "rt" in d.columns else 0.0
        d.to_parquet(a.out / "events.parquet", index=False)
    X = featurise(d); y = d["response"].to_numpy()
    fold = (pd.util.hash_array(d["uid"].to_numpy(np.int64)) % 2).astype(int)
    p = np.full(len(d), np.nan, np.float32)
    tr_mask = (d["split"] == "train").to_numpy()
    for f in range(2):
        fit = tr_mask & (fold != f)
        m = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=100,
                                           l2_regularization=1.0, random_state=f).fit(X[fit], y[fit])
        apply = (fold == f)
        p[apply] = m.predict_proba(X[apply])[:, 1]
    for split in ["train", "test"]:
        mm = (d["split"] == split).to_numpy()
        out = d.loc[mm, ["uid", "seq_pos"]].copy(); out["p_dkt"] = p[mm]
        out.to_parquet(a.out / f"p_dkt_{split}.parquet", index=False)
        print(f"{split}: n={mm.sum()} AUC={roc_auc_score(y[mm], p[mm]):.4f} ACC={((p[mm] > .5) == y[mm]).mean():.4f}")


if __name__ == "__main__":
    main()

"""Stage 0 - fit half-life regression (Settles & Meeder 2016) on the Duolingo
spaced-repetition traces, restricted to one language pair, to get theta for the
p_hlr feature / baseline used on SLAM.

Model: p = 2^(-delta_days / h),  h = 2^(theta . x),  x = [1, sqrt(1+seen), sqrt(1+correct), sqrt(1+wrong)]
Fitted by minimising mean squared error in p plus L2 on theta (Adam, NumPy). Reports
MAE / AUC on a held-out 20% and the review-recall-by-lag curve used in the report.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

COLS = ["p_recall", "timestamp", "delta", "user_id", "learning_language", "ui_language", "lexeme_id",
        "lexeme_string", "history_seen", "history_correct", "session_seen", "session_correct"]


def load(zpath: Path, learn: str, ui: str, cap: int) -> pd.DataFrame:
    if zpath.suffix == ".zip":
        z = zipfile.ZipFile(zpath)
        name = [n for n in z.namelist() if n.endswith(".csv") and not n.startswith("__")][0]
        src = z.open(name)
    else:
        src = zpath
    parts = []
    for chunk in pd.read_csv(src, usecols=["p_recall", "delta", "learning_language", "ui_language",
                                           "history_seen", "history_correct", "user_id"], chunksize=1_000_000):
        c = chunk[(chunk["learning_language"] == learn) & (chunk["ui_language"] == ui)]
        parts.append(c)
        if sum(len(p) for p in parts) >= cap:
            break
    return pd.concat(parts).head(cap).reset_index(drop=True)


def features(seen, correct):
    wrong = seen - correct
    return np.stack([np.ones(len(seen)), np.sqrt(1 + seen), np.sqrt(1 + correct), np.sqrt(1 + wrong)], 1).astype(np.float32)


def fit(X, dd, p, iters=3000, lr=0.02, l2=0.01, seed=0):
    rng = np.random.default_rng(seed)
    th = np.zeros(X.shape[1], np.float32); m = np.zeros_like(th); v = np.zeros_like(th)
    for it in range(1, iters + 1):
        idx = rng.integers(0, len(X), 50_000)
        x, d, y = X[idx], dd[idx], p[idx]
        h = 2.0 ** np.clip(x @ th, -8, 12)
        ph = 2.0 ** (-d / h)
        # d ph / d theta = ph * ln2 * (d/h) * ln2 * x   (since dh/dtheta = h ln2 x)
        g = ((ph - y) * ph * np.log(2) ** 2 * (d / h))[:, None] * x
        grad = 2 * g.mean(0) + 2 * l2 * th
        m = 0.9 * m + 0.1 * grad; v = 0.999 * v + 0.001 * grad ** 2
        th -= lr * (m / (1 - 0.9 ** it)) / (np.sqrt(v / (1 - 0.999 ** it)) + 1e-8)
    return th


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--learn", default="en"); ap.add_argument("--ui", default="es")
    ap.add_argument("--cap", type=int, default=1_500_000)
    a = ap.parse_args()
    d = load(a.zip, a.learn, a.ui, a.cap)
    print(f"{len(d)} traces, {d['user_id'].nunique()} users, mean p_recall {d['p_recall'].mean():.3f}")
    X = features(d["history_seen"].to_numpy(np.float32), d["history_correct"].to_numpy(np.float32))
    dd = (d["delta"].to_numpy(np.float32) / 86400).clip(1 / 1440, None)
    p = d["p_recall"].to_numpy(np.float32)
    uu = d["user_id"].astype("category").cat.codes.to_numpy()
    te = (pd.util.hash_array(uu.astype(np.int64)) % 5) == 0
    th = fit(X[~te], dd[~te], p[~te])
    h = 2.0 ** (X[te] @ th); ph = 2.0 ** (-dd[te] / h)
    mae = float(np.abs(ph - p[te]).mean()); auc = float(roc_auc_score((p[te] >= 1.0).astype(int), ph))
    base_mae = float(np.abs(p[~te].mean() - p[te]).mean())
    # recall by lag bucket (the empirical forgetting curve)
    lag_bins = pd.cut(dd, [0, 1 / 24, 1, 7, 30, 1e9], labels=["<1h", "1h-1d", "1d-1w", "1w-30d", ">30d"])
    curve = d.groupby(lag_bins, observed=True)["p_recall"].agg(["mean", "size"]).round(3)
    res = {"theta": th.tolist(), "n_train": int((~te).sum()), "n_test": int(te.sum()), "mae": mae,
           "mae_constant": base_mae, "auc_perfect_recall": auc, "recall_by_lag": curve.to_dict()}
    json.dump(res, open(a.out / "hlr_theta.json", "w"), indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()

"""Phase 4 extension: how the released DKT's predicted lift accumulates with the number of flipped mistakes.

Run from the repo root, after score_events.py:
    uv run python src/calibration/score_multiflip.py --kc_level 2 2>&1 | tee docs/exploration/$(date +%F)_rq3_multiflip.log

For each matched correction pair in the test split, the control student's history is edited by
flipping k of their earlier wrong answers to correct (the first attempt at the matched question
always included; the other k-1 drawn at random among wrong answers before it, seed 2026), for
k = 1, 2, 5, 10, 25 and "half" (half of all wrong answers before the first attempt, the count
KTCF's sign rule produces). The model is then scored on the same next-10 same-strand window as
H2c, and the predicted lift over the unedited history is reported per k, with cluster-bootstrap
CIs by treated student. The observed single-correction lift from H2c is printed alongside for
reference; there is no observed analogue of flipping 25 or 54 answers, which is the point.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
REPO = Path(__file__).resolve().parents[2]
_ap = argparse.ArgumentParser()
_ap.add_argument("--kc_level", type=int, default=2)
_ap.add_argument("--maxlen", type=int, default=500)
ARGS = _ap.parse_args()
KC_TAG = f"kclevel{ARGS.kc_level}"
MAXLEN = ARGS.maxlen
IN = REPO / "data/processed/xes3g5m_clean.parquet"
PAIRS = REPO / "data/processed/rq2" / f"rq2_h2c_pairs_{KC_TAG}.csv"
OUT = REPO / "data/processed/rq3"

KTCF_ROOT = Path(os.environ.get("KTCF_ROOT", "../ktcf-work")).resolve()
os.chdir(KTCF_ROOT)
sys.path.insert(0, str(KTCF_ROOT)); sys.path.insert(0, str(KTCF_ROOT / "src"))

import copy  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402

from pykt.models import load_model  # noqa: E402

SEED, BOOT = 2026, 1000
rng = np.random.default_rng(SEED); torch.manual_seed(SEED)
KS = [1, 2, 5, 10, 25, "half"]

with open("./saved_model/config.json") as fin:
    config = json.load(fin); model_config = copy.deepcopy(config["model_config"])
    for k in ["use_wandb", "learning_rate", "add_uuid", "l2"]:
        model_config.pop(k, None)
    tp = config["params"]
with open("./configs/data_config.json") as fin:
    data_config = copy.deepcopy(json.load(fin))[tp["dataset_name"]]
    data_config["dataset_name"] = tp["dataset_name"]; data_config["dpath"] = "./data/XES3G5M"
model = load_model(tp["model_name"], model_config, data_config, tp["emb_type"], "./saved_model"); model.eval()


@torch.no_grad()
def predict_positions(q, r, positions):
    end = max(positions) + 1; start = max(0, end - MAXLEN)
    y = model(torch.tensor(q[start:end][:-1]).unsqueeze(0), torch.tensor(r[start:end][:-1]).float().unsqueeze(0))[0]
    return np.array([float(y[p - start - 1, q[p]]) if p - start >= 1 else np.nan for p in positions])


def cluster_boot_mean(y, uid, B=BOOT):
    y, uid = np.asarray(y, float), np.asarray(uid)
    u, inv = np.unique(uid, return_inverse=True)
    s = np.bincount(inv, weights=y, minlength=len(u)); n = np.bincount(inv, minlength=len(u)).astype(float)
    w = rng.multinomial(len(u), np.full(len(u), 1 / len(u)), size=B); b = (w @ s) / (w @ n)
    lo, hi = np.percentile(b, [2.5, 97.5]); return float(s.sum() / n.sum()), float(lo), float(hi)


df = pd.read_parquet(IN, columns=["split", "uid", "response", "seq_pos", "first_kc"])
df = df[df["split"] == "test"].sort_values(["uid", "seq_pos"])
seqs = {uid: (g["first_kc"].to_numpy(np.int64), g["response"].to_numpy(np.int64)) for uid, g in df.groupby("uid", sort=False)}

pairs = pd.read_csv(PAIRS)
pairs = pairs[(pairs["split"] == "test") & (pairs["kind"] == "correction")]
rows = []
for row in pairs.itertuples(index=False):
    post = json.loads(row.post_pos_c)
    if len(post) < 10:
        continue
    q, r = seqs[row.uid_c]
    base = predict_positions(q, r, post).mean()
    wrong_before = np.flatnonzero(r[:row.first_pos_c] == 0)       # wrong answers strictly before the first attempt
    rec = dict(uid_t=row.uid_t, n_wrong_before=len(wrong_before), pred_base=base)
    for k in KS:
        kk = len(wrong_before) // 2 if k == "half" else k
        extra = rng.choice(wrong_before, size=min(kk - 1 if k != "half" else kk, len(wrong_before)), replace=False) if kk > 0 else np.array([], int)
        r_k = r.copy(); r_k[row.first_pos_c] = 1; r_k[extra] = 1
        rec[f"lift_{k}"] = predict_positions(q, r_k, post).mean() - base
        rec[f"nflip_{k}"] = 1 + len(extra)
    rows.append(rec)
R = pd.DataFrame(rows)
R.to_csv(OUT / f"rq3_C_multiflip_pairs_{KC_TAG}.csv", index=False)

out = []
for k in KS:
    e, lo, hi = cluster_boot_mean(R[f"lift_{k}"], R["uid_t"])
    out.append(dict(k=str(k), mean_flipped=float(R[f"nflip_{k}"].mean()), pred_lift=e, ci=f"[{lo:.3f}, {hi:.3f}]",
                    lift_per_flip=e / R[f"nflip_{k}"].mean()))
T = pd.DataFrame(out)
T.to_csv(OUT / f"rq3_C_multiflip_{KC_TAG}.csv", index=False)
print(f"pairs: {len(R)}; mean wrong answers before the first attempt: {R.n_wrong_before.mean():.1f}")
print("observed single-correction lift (H2c, test pairs): see rq3_B obs_lift\n")
show = T.copy()
for c in ["mean_flipped", "pred_lift", "lift_per_flip"]:
    show[c] = show[c].map(lambda x: f"{x:.3f}")
print(show.to_markdown(index=False))
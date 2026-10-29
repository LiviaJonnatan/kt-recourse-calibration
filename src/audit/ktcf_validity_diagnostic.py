"""Does KTCF's validity survive binarization, and how much is decided at initialization?

Run from this repo's root:
    uv run python src/audit/ktcf_validity_diagnostic.py

Reproduces run.py's setup exactly (same seeds, same 200-student sample, same
call order into initialize_response / generate_cf_dkt, so the random stream
matches the Table 1 run), then for each student records the model's prediction
at the target under:

  a  original responses
  b  cf_r at initialization, as run.py feeds it on step 0 (noise on all positions)
  b_m  same, with the actionability mask already applied (noise only on wrong answers)
  c  final cf_r as KTCF evaluates it (raw continuous)
  d  final cf_r binarized by sigmoid > 0.5 (eval_metrics' sparsity rule), mask re-applied
  d2 final cf_r binarized by cf_r > 0.5 (the rule inside the optimizer loop), mask re-applied

plus sparsity at init and final, and "index drift": the number of positions whose
soft-embedding lookup lands on a different concept than the one the student saw
(because x = q + num_c * r interpolates across the flattened index).

Writes <repo>/docs/exploration/<date>_ktcf_validity_diagnostic.csv and prints a summary.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
REPO = Path(__file__).resolve().parents[2]

import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--init_scheme", type=int, default=1, help="1=rn, 2=rand, 3=sr, 4=cc, 5=gs")
ARGS = _ap.parse_args()
SCHEME = {1: "rn", 2: "rand", 3: "sr", 4: "cc", 5: "gs"}[ARGS.init_scheme]
OUT = REPO / "docs" / "exploration" / f"{date.today().isoformat()}_ktcf_validity_diagnostic_{SCHEME}.csv"

KTCF_ROOT = Path(os.environ.get("KTCF_ROOT", "../ktcf-work")).resolve()
os.chdir(KTCF_ROOT)                     # run.py uses ./ paths
sys.path.insert(0, str(KTCF_ROOT))      # pykt, ktcf
sys.path.insert(0, str(KTCF_ROOT / "src"))

os.environ["PYTHONHASHSEED"] = "42"

import ast  # noqa: E402
import copy  # noqa: E402
import json  # noqa: E402
import pickle  # noqa: E402
import random  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

from ktcf.cf_generator import KTCF  # noqa: E402
from ktcf.init_cf import initialize_response  # noqa: E402
from pykt.models import load_model  # noqa: E402


def set_all_seeds(seed=42):
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.use_deterministic_algorithms(True)


set_all_seeds(42)
device = "cpu"

# ---- identical to run.py ----
with open("./saved_model/config.json") as fin:
    config = json.load(fin)
    model_config = copy.deepcopy(config["model_config"])
    for k in ["use_wandb", "learning_rate", "add_uuid", "l2"]:
        model_config.pop(k, None)
    tp = config["params"]
    model_name, dataset_name, emb_type = tp["model_name"], tp["dataset_name"], tp["emb_type"]
with open("./configs/data_config.json") as fin:
    data_config = copy.deepcopy(json.load(fin))[dataset_name]
    data_config["dataset_name"] = dataset_name
    data_config["dpath"] = "./data/XES3G5M"
model = load_model(model_name, model_config, data_config, emb_type, "./saved_model")
num_c = model.num_c

kc_info = pd.read_csv("./data/XES3G5M/metadata/kc_nodes.csv")
with open("./data/XES3G5M/metadata/shortest_paths.pkl", "rb") as f:
    shortest_info = pickle.load(f)
test_predictions = pd.read_csv("./data/XES3G5M/XES3G5M_test_predictions_45_zeros.csv").sample(n=200, random_state=42)

params = dict(alg="ktcf", init_scheme=ARGS.init_scheme, lr=0.01, max_iter=200, init_noise_std=0.1,
              init_lambda_convex=0.5, init_temp=0.1, lambda_pred=1.0, lambda_prox=0.1,
              lambda_kc=0.001, lambda_div=0.001, early_stopping_eta=1e-4, verbose=False, save_result=False)

print("init_scheme:", params["init_scheme"], "->", SCHEME)

ktcf = KTCF(model)
# -----------------------------


def pred_at(q, r, cshft, t) -> float:
    """Prediction at target for a (possibly soft) response vector, dropout off."""
    model.eval()
    with torch.no_grad():
        y = model(q, r)
        y = (y * F.one_hot(cshft.long(), num_c)).sum(-1)
    return y[0, t].item()


def index_drift(q, r) -> int:
    """Positions whose soft-embedding lookup floor index is neither (q, wrong) nor (q, right)."""
    x = q.float() + num_c * r
    lo = torch.floor(x.clamp(0, 2 * num_c - 1))
    ok = (lo == q.float()) | (lo == q.float() + num_c)
    return int((~ok).sum().item())


rows = []
for i, row in test_predictions.iterrows():
    q = torch.tensor(ast.literal_eval(row.concept)).unsqueeze(0)
    r = torch.tensor(ast.literal_eval(row.response)).unsqueeze(0).float()
    cshft = torch.tensor(ast.literal_eval(row.concept_shift)).unsqueeze(0)
    t = int(row.target_timestep)
    mask = (r == 0).float()
    n_wrong = int(mask.sum().item())

    a = pred_at(q, r, cshft, t)

    cf0 = initialize_response(params, r)                 # same RNG draw as run.py
    cf0_raw = cf0.detach().clone()
    cf0_masked = mask * cf0_raw + (1 - mask) * r
    b = pred_at(q, cf0_raw, cshft, t)
    b_m = pred_at(q, cf0_masked, cshft, t)
    spars_init = int(((torch.sigmoid(cf0_masked) > 0.5).float() != r).sum().item())
    drift_init = index_drift(q, cf0_masked)

    cf, pred_c_reported, _ = ktcf.generate_cf_dkt(
        params, q, r, cf0, cshft, target_timestep=t, node_info=kc_info, shortest_info=shortest_info,
        lr=params["lr"], max_iter=params["max_iter"], lambda_pred=params["lambda_pred"],
        lambda_prox=params["lambda_prox"], lambda_kc=params["lambda_kc"],
        early_stopping_eta=params["early_stopping_eta"], verbose=False)
    c = pred_at(q, cf, cshft, t)

    d_vec = mask * (torch.sigmoid(cf) > 0.5).float() + (1 - mask) * r
    d2_vec = mask * (cf > 0.5).float() + (1 - mask) * r
    d = pred_at(q, d_vec, cshft, t)
    d2 = pred_at(q, d2_vec, cshft, t)

    rows.append(dict(
        uid_row=i, target=t, n_wrong=n_wrong,
        pred_a_original=a, pred_b_init_raw=b, pred_b_init_masked=b_m,
        pred_c_final_soft=c, pred_c_reported=float(pred_c_reported),
        pred_d_binarized_sigmoid=d, pred_d2_binarized_half=d2,
        sparsity_init=spars_init,
        sparsity_final=int((d_vec != r).sum().item()),
        sparsity_final_half=int((d2_vec != r).sum().item()),
        drift_init=drift_init, drift_final=index_drift(q, cf),
        cf_min=float(cf.min()), cf_max=float(cf.max()),
    ))
    if len(rows) % 20 == 0:
        print(f"{len(rows)}/200")

df = pd.DataFrame(rows)
OUT.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUT, index=False)

v = lambda col: (df[col] > 0.5).mean()  # noqa: E731
print("\nValidity rate (pred at target > 0.5), n=200")
print(f"  a   original responses            {v('pred_a_original'):.3f}  (should be 0: targets were chosen as predicted-wrong)")
print(f"  b   init, raw (all positions)      {v('pred_b_init_raw'):.3f}")
print(f"  b_m init, masked (wrong only)      {v('pred_b_init_masked'):.3f}")
print(f"  c   final soft cf_r (KTCF's view)  {v('pred_c_final_soft'):.3f}   reported by generator: {v('pred_c_reported'):.3f}")
print(f"  d   final, binarized sigmoid>0.5   {v('pred_d_binarized_sigmoid'):.3f}")
print(f"  d2  final, binarized cf_r>0.5      {v('pred_d2_binarized_half'):.3f}")
print("\nSparsity (positions differing from original)")
print(f"  at init (sigmoid rule): mean {df.sparsity_init.mean():.1f}   final (sigmoid rule): {df.sparsity_final.mean():.1f}   final (>0.5 rule): {df.sparsity_final_half.mean():.1f}")
print(f"  wrong answers per student: mean {df.n_wrong.mean():.1f}  -> half of that: {df.n_wrong.mean()/2:.1f}")
print("\nSoft-embedding index drift (positions whose lookup is on a different concept)")
print(f"  at init: mean {df.drift_init.mean():.1f} of 199   final: mean {df.drift_final.mean():.1f}")
print(f"  cf_r range over all instances: [{df.cf_min.min():.2f}, {df.cf_max.max():.2f}]")
print(f"\nwrote {OUT}")
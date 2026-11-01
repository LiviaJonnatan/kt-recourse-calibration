"""Phase 4 (minimal): calibration of the released KTCF DKT checkpoint against observed re-attempt outcomes.

Run from the repo root, after observed_effects.py has written the pairs file:
    uv run python src/calibration/score_events.py --kc_level 2 2>&1 | tee docs/exploration/$(date +%F)_rq3_score_events.log

Reads   data/processed/xes3g5m_clean.parquet
        data/processed/item_difficulty.csv, data/raw/XES3G5M/metadata/questions.json
        data/processed/rq2/rq2_h2c_pairs_kclevel<N>.csv        (from observed_effects.py --kc_level N)
        the KTCF checkpoint under KTCF_ROOT (same loading code as ktcf_validity_diagnostic.py)
Writes  data/processed/rq3/*.csv and prints each table.

Everything is on the TEST split only: the checkpoint was trained on the train split.

Model input. The checkpoint is KC-level DKT (num_c = 865). A student's history is encoded as one
(first_kc, response) pair per interaction, in seq_pos order. pyKT's own preprocessing expands a
multi-KC question into one row per KC; we do not, so the encoding differs for multi-KC questions
(a minority). The sanity check below reports the checkpoint's AUC on these sequences; it should be
near the paper's 0.8226. Histories longer than MAXLEN are truncated to the last MAXLEN interactions
ending at the last position needed (the checkpoint was trained on sequences of length <= 200).

(A) Re-attempt calibration. For every test-split correction event: p = P(correct at the repeat |
    history before it). Reliability table (10 equal-width bins), ECE, Brier, AUC; by gap class,
    question type, difficulty tercile.

(B) Counterfactual-lift calibration, on the matched pairs. The intervention is KTCF's, binarized:
    set the response at the first attempt to 1, leave everything else as it was. For each pair:
      control arm   delta_pred_c = mean P(post window | flipped history) - mean P(post window | actual)
                    (no real repeat in the control history, so the flip is the only change)
      treated arm   delta_pred_t = mean P(post window | actual, which contains the repeat)
                                 - mean P(post window | actual with the repeat removed)
    compared with the observed matched difference from observed_effects.py:
      delta_obs = (post_acc_t - pre_acc_t) - (post_acc_c - pre_acc_c)
    Also reported: predicted vs observed post-window accuracy for each arm (level calibration).
    All means with 95% cluster-bootstrap CIs (treated student as the cluster), seed 2026.
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
_ap.add_argument("--sanity_students", type=int, default=300)
ARGS = _ap.parse_args()
KC_TAG = f"kclevel{ARGS.kc_level}"
MAXLEN = ARGS.maxlen

IN = REPO / "data/processed/xes3g5m_clean.parquet"
DIFF = REPO / "data/processed/item_difficulty.csv"
QJSON = REPO / "data/raw/XES3G5M/metadata/questions.json"
PAIRS = REPO / "data/processed/rq2" / f"rq2_h2c_pairs_{KC_TAG}.csv"
OUT = REPO / "data/processed/rq3"
OUT.mkdir(parents=True, exist_ok=True)

KTCF_ROOT = Path(os.environ.get("KTCF_ROOT", "../ktcf-work")).resolve()
os.chdir(KTCF_ROOT)
sys.path.insert(0, str(KTCF_ROOT))
sys.path.insert(0, str(KTCF_ROOT / "src"))

import copy  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402

from pykt.models import load_model  # noqa: E402

SEED = 2026
BOOT = 1000
rng = np.random.default_rng(SEED)
torch.manual_seed(SEED)
TYPE_MAP = {"填空": "fill-in", "单选": "single-choice", "选择": "choice"}

# ----------------------------------------------------------------------------- model (as in the diagnostic)
with open("./saved_model/config.json") as fin:
    config = json.load(fin)
    model_config = copy.deepcopy(config["model_config"])
    for k in ["use_wandb", "learning_rate", "add_uuid", "l2"]:
        model_config.pop(k, None)
    tp = config["params"]
with open("./configs/data_config.json") as fin:
    data_config = copy.deepcopy(json.load(fin))[tp["dataset_name"]]
    data_config["dataset_name"] = tp["dataset_name"]
    data_config["dpath"] = "./data/XES3G5M"
model = load_model(tp["model_name"], model_config, data_config, tp["emb_type"], "./saved_model")
model.eval()
num_c = model.num_c


@torch.no_grad()
def predict_positions(q: np.ndarray, r: np.ndarray, positions: list[int]) -> np.ndarray:
    """P(correct) at each position in `positions` (indices into q/r), given the history before it.
    DKT's output at step i-1 scores concept q[i] at step i."""
    end = max(positions) + 1
    start = max(0, end - MAXLEN)
    qq = torch.tensor(q[start:end][:-1]).unsqueeze(0)
    rr = torch.tensor(r[start:end][:-1]).float().unsqueeze(0)
    y = model(qq, rr)[0]                                   # (end-start-1, num_c)
    out = []
    for p in positions:
        i = p - start
        out.append(float(y[i - 1, q[p]]) if i >= 1 else np.nan)
    return np.array(out)


# ----------------------------------------------------------------------------- data
df = pd.read_parquet(IN, columns=["split", "uid", "question", "response", "seq_pos", "attempt", "is_repeat",
                                  "gap_class", "kind", "first_kc", "prev_seq_pos"])
df = df[df["split"] == "test"].sort_values(["uid", "seq_pos"])
df = df.merge(pd.read_csv(DIFF, usecols=["question", "tercile"]), on="question", how="left")
df["tercile"] = df["tercile"].fillna("no tercile")
with open(QJSON, encoding="utf-8") as f:
    qmeta = json.load(f)
df["qtype"] = df["question"].map({int(k): TYPE_MAP.get(v.get("type"), "unknown") for k, v in qmeta.items()}).fillna("unknown")

seqs = {uid: (g["first_kc"].to_numpy(np.int64), g["response"].to_numpy(np.int64), g["seq_pos"].to_numpy())
        for uid, g in df.groupby("uid", sort=False)}
for uid, (q, r, sp) in seqs.items():                       # seq_pos must be 0..n-1 for direct indexing
    assert (sp == np.arange(len(sp))).all(), f"non-contiguous seq_pos for uid {uid}"


# ----------------------------------------------------------------------------- helpers
def roc_auc_score(y, p) -> float:
    """Rank-based AUC (Mann-Whitney), ties averaged; no sklearn dependency."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    order = np.argsort(p, kind="mergesort"); ranks = np.empty(len(p)); ranks[order] = np.arange(1, len(p) + 1)
    _, inv, cnt = np.unique(p, return_inverse=True, return_counts=True)
    if (cnt > 1).any():                                     # average ranks over ties
        sums = np.bincount(inv, weights=ranks); ranks = sums[inv] / cnt[inv]
    n1, n0 = y.sum(), len(y) - y.sum()
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")


def cluster_boot_mean(y, uid, B=BOOT):
    y, uid = np.asarray(y, float), np.asarray(uid)
    u, inv = np.unique(uid, return_inverse=True)
    s = np.bincount(inv, weights=y, minlength=len(u)); n = np.bincount(inv, minlength=len(u)).astype(float)
    w = rng.multinomial(len(u), np.full(len(u), 1 / len(u)), size=B)
    boots = (w @ s) / (w @ n)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(s.sum() / n.sum()), float(lo), float(hi)


def calibration_table(p, y, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    rows, ece = [], 0.0
    for b in range(bins):
        m = idx == b
        if m.sum() == 0:
            continue
        conf, acc = p[m].mean(), y[m].mean()
        ece += m.mean() * abs(conf - acc)
        rows.append(dict(bin=f"[{edges[b]:.1f},{edges[b+1]:.1f})", n=int(m.sum()), mean_pred=conf, observed=acc, gap=acc - conf))
    return pd.DataFrame(rows), float(ece)


def summary(p, y, uid):
    pe, plo, phi = cluster_boot_mean(p, uid); ye, ylo, yhi = cluster_boot_mean(y, uid)
    _, ece = calibration_table(p, y)
    auc = roc_auc_score(y, p) if 0 < y.mean() < 1 else np.nan
    return dict(n=len(y), students=len(np.unique(uid)), mean_pred=pe, pred_ci=f"[{plo:.3f}, {phi:.3f}]",
                observed=ye, obs_ci=f"[{ylo:.3f}, {yhi:.3f}]", gap=ye - pe, ece=ece,
                brier=float(np.mean((p - y) ** 2)), auc=float(auc))


def emit(name, t):
    t.to_csv(OUT / f"{name}.csv", index=False)
    show = t.copy()
    for c in show.columns:
        if show[c].dtype.kind == "f":
            show[c] = show[c].map(lambda x: f"{x:.3f}")
    print(f"\n### {name}\n"); print(show.to_markdown(index=False))


# ----------------------------------------------------------------------------- sanity: AUC of the checkpoint on our encoding
uids = rng.choice(list(seqs), size=min(ARGS.sanity_students, len(seqs)), replace=False)
ps, ys = [], []
for uid in uids:
    q, r, _ = seqs[uid]
    pos = list(range(1, min(len(q), MAXLEN)))
    ps.append(predict_positions(q, r, pos)); ys.append(r[pos])
ps, ys = np.concatenate(ps), np.concatenate(ys)
print(f"sanity: checkpoint AUC on {len(uids)} test students, first_kc encoding, positions 1..{MAXLEN-1}: "
      f"{roc_auc_score(ys, ps):.4f}  (paper: 0.8226)   acc {((ps > 0.5) == ys).mean():.4f}")

# ----------------------------------------------------------------------------- (A) re-attempt calibration
ev = df[(df["is_repeat"]) & (df["kind"] == "correction")].copy()
ev["gap_class"] = ev["gap_class"].astype(str)
pred = np.full(len(ev), np.nan)
for i, (uid, pos) in enumerate(zip(ev["uid"], ev["seq_pos"])):
    q, r, _ = seqs[uid]
    pred[i] = predict_positions(q, r, [int(pos)])[0]
ev["pred"] = pred
ev = ev[ev["pred"].notna()]
y, p, u = ev["response"].to_numpy(float), ev["pred"].to_numpy(), ev["uid"].to_numpy()
rows = [dict(subset="all", **summary(p, y, u))]
for col in ["gap_class", "qtype", "tercile"]:
    for v in sorted(ev[col].unique()):
        m = (ev[col] == v).to_numpy()
        if m.sum() >= 30:
            rows.append(dict(subset=f"{col}={v}", **summary(p[m], y[m], u[m])))
emit("rq3_A_reattempt_calibration", pd.DataFrame(rows))
tab, ece = calibration_table(p, y)
emit("rq3_A_reattempt_reliability_all", tab)
ev[["uid", "question", "seq_pos", "gap_class", "qtype", "tercile", "response", "pred"]].to_csv(OUT / "rq3_A_events.csv", index=False)

# ----------------------------------------------------------------------------- (B) counterfactual lift on matched pairs
pairs = pd.read_csv(PAIRS)
pairs = pairs[(pairs["split"] == "test") & (pairs["kind"] == "correction")].reset_index(drop=True)
print(f"\nmatched correction pairs in test split: {len(pairs)}")

rec = []
for row in pairs.itertuples(index=False):
    post_t = json.loads(row.post_pos_t); post_c = json.loads(row.post_pos_c)
    if len(post_t) < 10 or len(post_c) < 10:
        continue
    # control arm: actual vs first attempt flipped to correct
    q, r, _ = seqs[row.uid_c]
    r_flip = r.copy(); r_flip[row.first_pos_c] = 1
    pc_actual = predict_positions(q, r, post_c); pc_flip = predict_positions(q, r_flip, post_c)
    # treated arm: actual (contains the repeat) vs the repeat removed
    q, r, _ = seqs[row.uid_t]
    pt_actual = predict_positions(q, r, post_t)
    q_rm, r_rm = np.delete(q, row.repeat_pos_t), np.delete(r, row.repeat_pos_t)
    post_t_rm = [p - 1 for p in post_t]                  # positions shift by one after removal
    pt_removed = predict_positions(q_rm, r_rm, post_t_rm)
    rec.append(dict(uid_t=row.uid_t, gap_class=row.gap_class, qtype=row.qtype, tercile=row.tercile,
                    repeat_success=row.repeat_response_t,
                    pred_post_c_actual=np.nanmean(pc_actual), pred_post_c_flip=np.nanmean(pc_flip),
                    pred_post_t_actual=np.nanmean(pt_actual), pred_post_t_removed=np.nanmean(pt_removed),
                    obs_post_c=row.post_acc_c, obs_post_t=row.post_acc_t, obs_pre_c=row.pre_acc_c, obs_pre_t=row.pre_acc_t))
R = pd.DataFrame(rec)
R["delta_pred_control_flip"] = R["pred_post_c_flip"] - R["pred_post_c_actual"]
R["delta_pred_treated_repeat"] = R["pred_post_t_actual"] - R["pred_post_t_removed"]
R["delta_obs_matched"] = (R["obs_post_t"] - R["obs_pre_t"]) - (R["obs_post_c"] - R["obs_pre_c"])
R["level_gap_treated"] = R["obs_post_t"] - R["pred_post_t_actual"]
R["level_gap_control"] = R["obs_post_c"] - R["pred_post_c_actual"]
R.to_csv(OUT / f"rq3_B_pairs_scored_{KC_TAG}.csv", index=False)

rows = []
subsets = [("all", np.ones(len(R), bool)), ("repeat succeeded", R["repeat_success"].to_numpy() == 1),
           ("repeat failed", R["repeat_success"].to_numpy() == 0)]
subsets += [(f"{c}={v}", (R[c] == v).to_numpy()) for c in ["gap_class", "qtype", "tercile"] for v in sorted(R[c].unique())]
for name, m in subsets:
    if m.sum() < 30:
        continue
    u = R["uid_t"].to_numpy()[m]
    row = dict(subset=name, n_pairs=int(m.sum()))
    for col, lab in [("delta_pred_control_flip", "pred_lift_flip"), ("delta_pred_treated_repeat", "pred_lift_repeat"),
                     ("delta_obs_matched", "obs_lift"), ("level_gap_treated", "obs_minus_pred_post_t"),
                     ("level_gap_control", "obs_minus_pred_post_c")]:
        e, lo, hi = cluster_boot_mean(R[col].to_numpy()[m], u)
        row[lab] = e; row[lab + "_ci"] = f"[{lo:.3f}, {hi:.3f}]"
    rows.append(row)
emit(f"rq3_B_counterfactual_lift_{KC_TAG}", pd.DataFrame(rows))
print(f"\nwrote tables to {OUT}/")
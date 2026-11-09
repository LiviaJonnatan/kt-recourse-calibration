"""(part 2) Load a trained pyKT model (dkt or dkt_forget) and write p_dkt_{train,test}.parquet in
our events.parquet row order, so stages 3-5 run unchanged with a real sequence model.

Run inside the pyKT environment (needs torch + pykt). For each learner the full sequence is fed in
one pass (pyKT trains on 200-step chunks; the LSTM runs on longer inputs fine). p_dkt for row t is
the prediction for row t's concept given rows < t (pyKT convention; row 0 = NaN).

Usage: python s14_pykt_predict.py --out ../../out/slam --pykt_data ../../data/pykt/slam \
          --ckpt_dir <pykt saved_model dir for the run> --model dkt            # or dkt_forget
"""
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd, torch
from pykt.models import init_model
import math

def _log2(t): return round(math.log(t + 1, 2))

def compute_dgaps(c, ts, dc):
    """Exact mirror of pykt DktForgetDataset.calC; ts in the same unit as the s13 export (seconds)."""
    rg_l, sg_l, pc_l = [], [], []
    last_c, cnt, pret = {}, {}, None
    for s, t in zip(c, ts):
        rg_l.append(0 if s not in last_c else _log2((t - last_c[s]) / 1000 / 60) + 1); last_c[s] = t
        sg_l.append(0 if pret is None else _log2((t - pret) / 1000 / 60) + 1); pret = t
        cnt.setdefault(s, 0); pc_l.append(_log2(cnt[s])); cnt[s] += 1
    rg = np.minimum(np.asarray(rg_l), dc["num_rgap"] - 1)
    sg = np.minimum(np.asarray(sg_l), dc["num_sgap"] - 1)
    pc = np.minimum(np.asarray(pc_l), dc["num_pcount"] - 1)
    T = lambda a: torch.tensor(np.asarray(a)[None, :], dtype=torch.long)
    return {"rgaps": T(rg[:-1]), "sgaps": T(sg[:-1]), "pcounts": T(pc[:-1]),
            "shft_rgaps": T(rg[1:]), "shft_sgaps": T(sg[1:]), "shft_pcounts": T(pc[1:])}

ap = argparse.ArgumentParser()
ap.add_argument("--out", type=Path, required=True); ap.add_argument("--pykt_data", type=Path, required=True)
ap.add_argument("--ckpt_dir", type=Path, required=True); ap.add_argument("--model", default="dkt")
ap.add_argument("--suffix", default="", help="e.g. _forget -> writes p_dkt_train_forget.parquet")
a = ap.parse_args()
cfg = json.load(open(a.ckpt_dir / "config.json"))
mp, dc = cfg["model_config"], cfg["data_config"]
for k in ["use_wandb", "learning_rate", "add_uuid", "l2", "num_epochs", "batch_size", "optimizer", "seed", "fold"]:
    mp.pop(k, None)
model = init_model(a.model, mp, dc, cfg["params"]["emb_type"]); model.load_state_dict(torch.load(a.ckpt_dir / f"{cfg['params']['emb_type']}_model.ckpt", map_location="cpu")); model.eval()
cmap = pd.read_csv(a.pykt_data / "concept_map.csv", dtype={"area": str}).set_index("area")["c"].to_dict()
qmap = pd.read_csv(a.pykt_data / "question_map.csv").set_index("question")["q"].to_dict()
d = pd.read_parquet(a.out / "events.parquet", columns=["split", "uid", "seq_pos", "question", "area", "response", "ts"]).sort_values(["uid", "seq_pos"])
d["c"] = d["area"].astype(str).map(cmap).astype(int)
d["q"] = d["question"].map(qmap).astype(int)
for split in ["train", "test"]:
    part = d[d.split == split]; p = np.full(len(part), np.nan, np.float32); pos = 0
    with torch.no_grad():
        for uid, g in part.groupby("uid", sort=False):
            c = torch.tensor(g["c"].to_numpy()[None, :-1]); r = torch.tensor(g["response"].to_numpy()[None, :-1]); q = torch.tensor(g["q"].to_numpy()[None, :-1])
            if a.model == "dkt":
                y = model(c.long(), r.long())
            else:
                dg = compute_dgaps(g["c"].to_numpy(), g["ts"].to_numpy() // 1000, dc)
                y = model(c.long(), r.long(), dg)
            y = y[0].numpy(); nxt = g["c"].to_numpy()[1:]
            p[pos + 1: pos + len(g)] = y[np.arange(len(g) - 1), nxt]; pos += len(g)
    out = part[["uid", "seq_pos"]].copy(); out["p_dkt"] = p
    out.to_parquet(a.out / f"p_dkt_{split}{a.suffix}.parquet", index=False); print(split, "written", int(np.isfinite(p).sum()))
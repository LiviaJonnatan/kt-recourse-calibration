"""Stage 4 - build a k-item study guide per student and score it (set level).

For each sampled test student, a decision point t is drawn (history >= 60). The
"target area" is the area of the interaction the student is about to do at t,
mirroring KTCF's target KC. Candidates are the student's distinct past questions
in the last `--lookback` positions; each candidate is a correction (last answer
wrong) or a review (last answer right), with covariates computed at time t.

Selectors (each returns k candidates)
    random
    dkt_pcorrect        DKT P(correct) on the candidate's KC at t, descending      [predicted-correctness]
    ktcf_flip           corrections only; delta in DKT P(target KC) from flipping the past wrong answer to right, descending [KTCF's objective, one-flip form]
    raw_gain            tau_t descending (effect model, no debiasing, no uncertainty)
    uplift_dr           tau_dr descending
    uplift_lcb          tau_t - z*sd descending
    uplift_lcb_area     uplift_lcb with at most one candidate per area
    uplift_full         uplift_lcb_area restricted to supported candidates (propensity >= support_min)

Per-set scores
    tau_dr_mean         model-estimated lift of the set (DR-learner)
    evaluability        share of chosen actions with propensity >= support_min
    e_mean              mean propensity (how often students like this one actually did this)
    sim_flip_valid      KTCF-style simulated validity: flip chosen corrections in the past, DKT P(target) > 0.5
    sim_append_p        append the chosen actions (answered correctly) at t, DKT P(target)
    realized_share      share of chosen questions the student actually re-attempted within the next 30 interactions
    realized_y          observed next-5 target-area accuracy after those realized re-attempts
    n_corr / n_rev      action mix; diff_mean; gap_mean
"""
from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from s2_dkt import DKT, load_dkt, NUM_C
from s3_uplift import SHARED, TREATED_EXTRA, Uplift  # noqa: F401  (Uplift needed for unpickle)

SEED = 11
SUPPORT_MIN = 0.02
Z = 1.0


def student_candidates(g: pd.DataFrame, t: int, lookback: int, diff: dict, single: dict, area_of: dict,
                       dkt: DKT, p_row: np.ndarray) -> pd.DataFrame:
    hist = g.iloc[:t]
    past = hist.iloc[max(0, t - lookback):]
    last = past.drop_duplicates("question", keep="last")
    ts_t = g["ts"].iloc[t]
    rows = []
    resp_all = hist["response"].to_numpy()
    for _, r in last.iterrows():
        area = area_of[int(r["question"])]
        in_area = hist["area"].to_numpy() == area
        ra = resp_all[in_area]
        rows.append({
            "question": int(r["question"]), "first_kc": int(r["first_kc"]), "area": area,
            "pos": int(r["seq_pos"]), "last_resp": int(r["response"]),
            "action": "correction" if r["response"] == 0 else "review",
            "pre_area": ra[-10:].mean() if len(ra) >= 3 else np.nan,
            "pre_all": resp_all[-20:].mean(), "hist": t, "n_area": int(in_area.sum()),
            "difficulty": diff.get(int(r["question"]), np.nan), "single": single[int(r["question"])],
            "p_dkt": float(p_row[int(r["first_kc"])]),
            "gap_log": float(np.log10(max((ts_t - r["ts"]) / 1000.0, 1.0))),
            "n_attempt": int((hist["question"] == r["question"]).sum()),
        })
    c = pd.DataFrame(rows)
    return c[c["pre_area"].notna() & c["difficulty"].notna()].reset_index(drop=True)


def flip_deltas(dkt: DKT, c_seq: np.ndarray, r_seq: np.ndarray, t: int, target_kc: int, positions: list[int]) -> np.ndarray:
    base = dkt.predict_all(c_seq[:t], r_seq[:t])[t - 1, target_kc]
    out = np.zeros(len(positions), np.float32)
    for i, p in enumerate(positions):
        r2 = r_seq[:t].copy(); r2[p] = 1
        out[i] = dkt.predict_all(c_seq[:t], r2)[t - 1, target_kc] - base
    return out, float(base)


def sim_flip(dkt, c_seq, r_seq, t, target_kc, positions) -> float:
    r2 = r_seq[:t].copy(); r2[positions] = 1
    return float(dkt.predict_all(c_seq[:t], r2)[t - 1, target_kc])


def sim_append(dkt, c_seq, r_seq, t, target_kc, kcs) -> float:
    c2 = np.concatenate([c_seq[:t], np.asarray(kcs, np.int64)]); r2 = np.concatenate([r_seq[:t], np.ones(len(kcs), np.int64)])
    return float(dkt.predict_all(c2, r2)[-1, target_kc])


def select(c: pd.DataFrame, name: str, k: int, rng) -> pd.DataFrame:
    if name == "random":
        return c.sample(min(k, len(c)), random_state=rng.integers(1 << 31))
    if name == "dkt_pcorrect":
        return c.nlargest(k, "p_dkt")
    if name == "ktcf_flip":
        return c[c["action"] == "correction"].nlargest(k, "flip_delta")
    if name == "raw_gain":
        return c.nlargest(k, "tau_t")
    if name == "uplift_dr":
        return c.nlargest(k, "tau_dr")
    if name == "uplift_lcb":
        return c.nlargest(k, "lcb")
    if name == "uplift_lcb_area":
        return c.sort_values("lcb", ascending=False).drop_duplicates("area").head(k)
    if name == "uplift_full":
        s = c[c["e"] >= SUPPORT_MIN]
        return s.sort_values("lcb", ascending=False).drop_duplicates("area").head(k)
    raise ValueError(name)


SELECTORS = ["random", "dkt_pcorrect", "ktcf_flip", "raw_gain", "uplift_dr", "uplift_lcb", "uplift_lcb_area", "uplift_full"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--n_students", type=int, default=300)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--lookback", type=int, default=60)
    a = ap.parse_args()
    rng = np.random.default_rng(SEED)
    dkt = DKT(load_dkt(a.ckpt))
    ups = {arm: pickle.load(open(a.out / f"uplift_{arm}.pkl", "rb")) for arm in ["correction", "review"]}
    d = pd.read_parquet(a.out / "events.parquet")
    d = d[d["split"] == "test"].sort_values(["uid", "seq_pos"])
    q = json.load(open(a.raw / "metadata/questions.json", encoding="utf-8-sig"))
    diff = d[["question", "difficulty"]].dropna().drop_duplicates("question").set_index("question")["difficulty"].to_dict()
    single = {int(k): int(v.get("type") == "单选") for k, v in q.items()}
    area_of = d[["question", "area"]].drop_duplicates("question").set_index("question")["area"].astype(str).to_dict()
    d["area"] = d["area"].astype(str)

    uids = d["uid"].unique()
    uids = rng.choice(uids, a.n_students, replace=False)
    rows = []
    for ui, uid in enumerate(uids):
        g = d[d["uid"] == uid].reset_index(drop=True)
        if len(g) < 100:
            continue
        t = int(rng.integers(60, len(g) - 30))
        target_kc = int(g["first_kc"].iloc[t]); target_area = g["area"].iloc[t]
        c_seq = g["first_kc"].to_numpy(np.int64); r_seq = g["response"].to_numpy(np.int64)
        p_row = dkt.predict_all(c_seq[:t], r_seq[:t])[t - 1]
        c = student_candidates(g, t, a.lookback, diff, single, area_of, dkt, p_row)
        if len(c) < a.k:
            continue
        # uplift scores (arm-specific models)
        for arm, up in ups.items():
            m = c["action"] == arm
            if m.any():
                sc = up.score(c[m])
                for col in sc.columns:
                    c.loc[m, col] = sc[col].to_numpy()
        c["lcb"] = c["tau_t"] - Z * c["tau_sd"]
        # KTCF one-flip deltas for corrections
        c["flip_delta"] = np.nan
        wrong = c[c["action"] == "correction"]
        if len(wrong):
            deltas, base = flip_deltas(dkt, c_seq, r_seq, t, target_kc, wrong["pos"].tolist())
            c.loc[wrong.index, "flip_delta"] = deltas
        else:
            base = float(p_row[target_kc])
        # realized re-attempts in the next 30 interactions
        fut = g.iloc[t:t + 30]
        realized_q = set(fut.loc[fut["n_attempt"] > 0, "question"].astype(int))
        fut_area = g.iloc[t:]
        for name in SELECTORS:
            s = select(c, name, a.k, rng)
            if len(s) == 0:
                rows.append({"uid": int(uid), "selector": name, "n_chosen": 0}); continue
            real = s["question"].isin(realized_q)
            realized_y = np.nan
            if real.any():
                ys = []
                for qq in s.loc[real, "question"]:
                    pos = fut.index[(fut["question"] == qq) & (fut["n_attempt"] > 0)][0]
                    after = g.iloc[pos + 1:]; after = after[(after["area"] == target_area) & (after["question"] != qq)]
                    if len(after) >= 5:
                        ys.append(after["response"].iloc[:5].mean())
                realized_y = float(np.mean(ys)) if ys else np.nan
            corr_pos = s.loc[s["action"] == "correction", "pos"].tolist()
            rows.append({
                "uid": int(uid), "selector": name, "n_chosen": len(s), "k": a.k,
                "tau_dr_mean": float(s["tau_dr"].mean()), "tau_t_mean": float(s["tau_t"].mean()),
                "mu0_mean": float(s["mu0"].mean()), "e_mean": float(s["e"].mean()),
                "evaluability": float((s["e"] >= SUPPORT_MIN).mean()),
                "base_p_target": base,
                "sim_flip_p": sim_flip(dkt, c_seq, r_seq, t, target_kc, corr_pos) if corr_pos else base,
                "sim_append_p": sim_append(dkt, c_seq, r_seq, t, target_kc, s["first_kc"].tolist()),
                "realized_share": float(real.mean()), "realized_y": realized_y,
                "n_corr": int((s["action"] == "correction").sum()), "n_rev": int((s["action"] == "review").sum()),
                "diff_mean": float(s["difficulty"].mean()), "gap_mean": float(s["gap_log"].mean()),
                "same_area_share": float((s["area"] == target_area).mean()),
                "n_candidates": len(c), "t": t,
            })
        if ui % 50 == 0:
            print(f"{ui}/{len(uids)} students done", flush=True)
    r = pd.DataFrame(rows)
    r.to_parquet(a.out / "s4_sets.parquet", index=False)
    r["sim_flip_valid"] = r["sim_flip_p"] > 0.5
    r["sim_append_valid"] = r["sim_append_p"] > 0.5
    agg = r.groupby("selector").agg(
        students=("uid", "nunique"), n_chosen=("n_chosen", "mean"),
        tau_dr=("tau_dr_mean", "mean"), tau_t=("tau_t_mean", "mean"), mu0=("mu0_mean", "mean"),
        e_mean=("e_mean", "mean"), evaluability=("evaluability", "mean"),
        sim_flip_valid=("sim_flip_valid", "mean"), sim_append_p=("sim_append_p", "mean"),
        realized_share=("realized_share", "mean"), realized_y=("realized_y", "mean"),
        n_realized=("realized_y", "count"), n_corr=("n_corr", "mean"), n_rev=("n_rev", "mean"),
        diff=("diff_mean", "mean"), gap=("gap_mean", "mean"), same_area=("same_area_share", "mean"),
    ).reindex(SELECTORS)
    agg.to_csv(a.out / "s4_set_summary.csv")
    pd.set_option("display.width", 250)
    print(agg.round(3).to_string())


if __name__ == "__main__":
    main()

"""Stage 4 (SLAM) - k-item study guides per learner, set-level scores, and case studies.

Same design as s4_select.py, with three SLAM-specific changes:
  * student model = the stage-2 gradient-boosted history model (no DKT here), so the
    KTCF-flip baseline recomputes P(target) after flipping a past answer in the learner's
    running aggregates (pre_all, pre_area, seen/correct of the token);
  * candidate pool = distinct tokens in the learner's last `--lookback` tokens (recency-bounded);
  * realized outcomes are dense: for each chosen token we look for the learner's next
    encounter with it in later exercises and read that event's y_next (next-5 same-POS
    accuracy after the re-attempt), and compare with the learner's own y_next at the decision
    point (what happened anyway).
Extra selector: hlr_lowest = spaced-repetition rule, review the item with the lowest predicted recall.
Writes s4_sets.parquet, s4_set_summary.csv and s4_cases.md (histories -> picks -> outcomes for a few learners).
"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from s2_student_slam import FEATS, featurise
import s3_uplift
from s3_uplift import Uplift  # noqa: F401
if "p_hlr" not in s3_uplift.TREATED_EXTRA:
    s3_uplift.TREATED_EXTRA.append("p_hlr")   # SLAM uplift models were fit with --extra p_hlr

SEED, SUPPORT_MIN, Z = 11, 0.02, 1.0
SELECTORS = ["random", "stud_pcorrect", "ktcf_flip", "hlr_lowest", "raw_gain", "uplift_dr", "uplift_lcb",
             "uplift_lcb_area", "uplift_full"]


def fit_student(d: pd.DataFrame, cap: int = 1_000_000):
    tr = d[d["split"] == "train"].sample(min(cap, (d["split"] == "train").sum()), random_state=0)
    return HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=100,
                                          l2_regularization=1.0, random_state=0).fit(featurise(tr), tr["response"].to_numpy())


def target_row(g: pd.DataFrame, t: int, hist_resp: np.ndarray) -> pd.DataFrame:
    """Recompute the target row's history features from (possibly flipped) past responses."""
    r = g.iloc[[t]].copy()
    area = g["area"].iloc[t]; q = g["question"].iloc[t]
    past = g.iloc[:t]
    r["pre_all"] = hist_resp[-20:].mean() if t >= 5 else np.nan
    ia = (past["area"].to_numpy() == area)
    ra = hist_resp[ia]; r["pre_area"] = ra[-10:].mean() if len(ra) >= 3 else np.nan
    iq = (past["question"].to_numpy() == q)
    r["seen"] = int(iq.sum()); r["correct"] = int(hist_resp[iq].sum()); r["wrong"] = r["seen"] - r["correct"]
    return r


def candidates(g: pd.DataFrame, t: int, lookback: int, diff: dict, stud, theta) -> pd.DataFrame:
    hist = g.iloc[:t]; past = hist.iloc[max(0, t - lookback):]
    last = past.drop_duplicates("question", keep="last")
    ts_t = g["ts"].iloc[t]; resp = hist["response"].to_numpy()
    rows = []
    for _, r in last.iterrows():
        area = r["area"]; ia = hist["area"].to_numpy() == area; ra = resp[ia]
        iq = hist["question"].to_numpy() == r["question"]
        seen = int(iq.sum()); correct = int(resp[iq].sum()); wrong = seen - correct
        lag_days = (ts_t - r["ts"]) / 86400000.0
        h = 2.0 ** (theta @ np.array([1, np.sqrt(1 + seen), np.sqrt(1 + correct), np.sqrt(1 + wrong)]))
        rows.append({"question": int(r["question"]), "question_str": r["question_str"], "area": area, "pos": int(r["seq_pos"]),
                     "last_resp": int(r["response"]), "action": "correction" if r["response"] == 0 else "review",
                     "pre_area": ra[-10:].mean() if len(ra) >= 3 else np.nan, "pre_all": resp[-20:].mean(),
                     "hist": t, "n_area": int(ia.sum()), "difficulty": diff.get(int(r["question"]), np.nan),
                     "single": int(r["single"]), "seen": seen, "correct": correct, "wrong": wrong,
                     "gap_log": float(np.log10(max(lag_days * 86400, 1.0))), "n_attempt": seen,
                     "p_hlr": float(2.0 ** (-lag_days / h)), "session": "practice", "format": r["format"], "rt": 0.0})
    c = pd.DataFrame(rows)
    c = c[c["pre_area"].notna() & c["difficulty"].notna()].reset_index(drop=True)
    if len(c):
        c["p_dkt"] = stud.predict_proba(featurise(c))[:, 1]
    return c


def select(c, name, k, rng):
    if name == "random": return c.sample(min(k, len(c)), random_state=rng.integers(1 << 31))
    if name == "stud_pcorrect": return c.nlargest(k, "p_dkt")
    if name == "ktcf_flip": return c[c["action"] == "correction"].nlargest(k, "flip_delta")
    if name == "hlr_lowest": return c.nsmallest(k, "p_hlr")
    if name == "raw_gain": return c.nlargest(k, "tau_t")
    if name == "uplift_dr": return c.nlargest(k, "tau_dr")
    if name == "uplift_lcb": return c.nlargest(k, "lcb")
    if name == "uplift_lcb_area": return c.sort_values("lcb", ascending=False).drop_duplicates("area").head(k)
    if name == "uplift_full":
        return c[c["e"] >= SUPPORT_MIN].sort_values("lcb", ascending=False).drop_duplicates("area").head(k)
    raise ValueError(name)


FUNCTION_POS = {"DET", "PRON", "ADP", "CONJ", "CCONJ", "SCONJ", "PART", "AUX", "PUNCT", "SYM", "X"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n_students", type=int, default=400)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--lookback", type=int, default=200)
    ap.add_argument("--horizon", type=int, default=100)
    ap.add_argument("--n_cases", type=int, default=3)
    ap.add_argument("--content_only", action="store_true")
    ap.add_argument("--outcome", default="y_next", help="y_next (area, per-area baseline) | y_item (next recall of picked token, vs non-picked realized candidates)")
    ap.add_argument("--model_tag", default="", help="suffix of uplift_{arm}<tag>.pkl")
    ap.add_argument("--headroom", type=float, default=None, help="only decision points with target-area pre_area < this")
    a = ap.parse_args()
    tag = ("_content" if a.content_only else "_all") + f"_{a.outcome}{a.model_tag}" + (f"_hr{a.headroom}" if a.headroom is not None else "")
    rng = np.random.default_rng(SEED)
    d = pd.read_parquet(a.out / "events.parquet"); d["area"] = d["area"].astype(str)
    theta = np.array(__import__("json").load(open(a.out / "hlr_theta.json"))["theta"])
    stud = fit_student(d)
    ups = {arm: pickle.load(open(a.out / f"uplift_{arm}{a.model_tag}.pkl", "rb")) for arm in ["correction", "review"]}
    diff = d[["question", "difficulty"]].dropna().drop_duplicates("question").set_index("question")["difficulty"].to_dict()
    test_uids = d.loc[d["split"] == "test", "uid"].unique()
    uids = rng.choice(test_uids, min(a.n_students, len(test_uids)), replace=False)
    rows, cases = [], []
    for ui, uid in enumerate(uids):
        g = d[d["uid"] == uid].sort_values("seq_pos").reset_index(drop=True)
        test_pos = g.index[g["split"] == "test"].to_numpy()
        test_pos = test_pos[(test_pos >= 200) & (test_pos < len(g) - a.horizon)]
        if len(test_pos) == 0:
            continue
        t = int(rng.choice(test_pos))
        if a.headroom is not None and not (g["pre_area"].iloc[t] < a.headroom):
            continue
        c = candidates(g, t, a.lookback, diff, stud, theta)
        if a.content_only:
            c = c[~c["area"].isin(FUNCTION_POS)].reset_index(drop=True)
        if len(c) < a.k:
            continue
        for arm, up in ups.items():
            m = c["action"] == arm
            if m.any():
                sc = up.score(c[m])
                for col in sc.columns:
                    c.loc[m, col] = sc[col].to_numpy()
        c["lcb"] = c["tau_t"] - Z * c["tau_sd"]
        resp = g["response"].to_numpy()[:t].copy()
        base = float(stud.predict_proba(featurise(target_row(g, t, resp)))[0, 1])
        c["flip_delta"] = np.nan
        for i in c.index[c["action"] == "correction"]:
            r2 = resp.copy(); r2[c.at[i, "pos"]] = 1
            c.at[i, "flip_delta"] = float(stud.predict_proba(featurise(target_row(g, t, r2)))[0, 1]) - base
        fut = g.iloc[t + 1:t + 1 + a.horizon]
        first_enc = (fut[fut["exercise_id"] != g["exercise_id"].iloc[t]]
                     .drop_duplicates("question", keep="first").set_index("question"))
        after = g.iloc[t + 1:]
        base_area = after.drop_duplicates("area", keep="first").set_index("area")["y_next"].to_dict()
        target_area = g["area"].iloc[t]
        y_anyway = float(g["y_next"].iloc[t])
        item_y = {q: first_enc.loc[q, "y_item"] for q in c["question"] if q in first_enc.index}
        item_y = {q: v for q, v in item_y.items() if not np.isnan(v)}
        picks = {}
        for name in SELECTORS:
            s = select(c, name, a.k, rng)
            if len(s) == 0:
                rows.append({"uid": int(uid), "selector": name, "n_chosen": 0}); continue
            enc = s["question"].isin(first_enc.index)
            gains, ry = [], []
            rr = [first_enc.loc[q, "response"] for q in s.loc[enc, "question"]]
            if a.outcome == "y_item":
                picked = [item_y[q] for q in s["question"] if q in item_y]
                others = [v for q, v in item_y.items() if q not in set(s["question"])]
                ry = picked
                if picked and others:
                    gains = [float(np.mean(picked) - np.mean(others))]
            else:
                for q, area in zip(s.loc[enc, "question"], s.loc[enc, "area"]):
                    y_after = first_enc.loc[q, "y_next"]; y_base = base_area.get(area, np.nan)
                    if not np.isnan(y_after):
                        ry.append(y_after)
                        if not np.isnan(y_base):
                            gains.append(y_after - y_base)
            picks[name] = s.assign(realized=enc.to_numpy())
            rows.append({"uid": int(uid), "selector": name, "n_chosen": len(s), "k": a.k, "t": t,
                         "tau_dr_mean": float(s["tau_dr"].mean()), "tau_t_mean": float(s["tau_t"].mean()),
                         "mu0_mean": float(s["mu0"].mean()), "e_mean": float(s["e"].mean()),
                         "evaluability": float((s["e"] >= SUPPORT_MIN).mean()), "base_p_target": base,
                         "realized_share": float(enc.mean()),
                         "realized_y": float(np.mean(ry)) if ry else np.nan,
                         "realized_gain": float(np.mean(gains)) if gains else np.nan,
                         "realized_correct": float(np.mean(rr)) if rr else np.nan, "y_anyway": y_anyway,
                         "n_corr": int((s["action"] == "correction").sum()), "n_rev": int((s["action"] == "review").sum()),
                         "diff_mean": float(s["difficulty"].mean()), "gap_mean": float(s["gap_log"].mean()),
                         "p_hlr_mean": float(s["p_hlr"].mean()), "same_area_share": float((s["area"] == target_area).mean()),
                         "n_candidates": len(c)})
        if len(cases) < a.n_cases:
            cases.append((uid, g, t, c, picks, base, y_anyway))
        if ui % 100 == 0:
            print(f"{ui}/{len(uids)}", flush=True)
    r = pd.DataFrame(rows)
    r.to_parquet(a.out / f"s4_sets{tag}.parquet", index=False)
    agg = r.groupby("selector").agg(
        students=("uid", "nunique"), tau_t=("tau_t_mean", "mean"), mu0=("mu0_mean", "mean"), e_mean=("e_mean", "mean"),
        realized_share=("realized_share", "mean"), realized_y=("realized_y", "mean"),
        realized_gain=("realized_gain", "mean"), n_realized=("realized_gain", "count"),
        realized_correct=("realized_correct", "mean"), n_corr=("n_corr", "mean"), n_rev=("n_rev", "mean"),
        diff=("diff_mean", "mean"), gap=("gap_mean", "mean"), p_hlr=("p_hlr_mean", "mean")).reindex(SELECTORS)
    cis = {}
    for name, grp in r.groupby("selector"):
        v = grp["realized_gain"].dropna().to_numpy()
        if len(v) > 10:
            b = [rng.choice(v, len(v)).mean() for _ in range(1000)]
            cis[name] = (np.percentile(b, 2.5), np.percentile(b, 97.5))
    agg["gain_ci_lo"] = pd.Series({k: v[0] for k, v in cis.items()}); agg["gain_ci_hi"] = pd.Series({k: v[1] for k, v in cis.items()})
    agg.to_csv(a.out / f"s4_set_summary{tag}.csv")
    pd.set_option("display.width", 250); print(agg.round(3).to_string())
    write_cases(cases, a.out / f"s4_cases{tag}.md", a.k)


def fmt_gap(gl: float) -> str:
    s = 10 ** gl
    return f"{s/60:.0f} min" if s < 3600 else (f"{s/3600:.1f} h" if s < 86400 else f"{s/86400:.1f} d")


def write_cases(cases, path: Path, k: int) -> None:
    L = ["# Case studies: three learners, history -> picks -> what happened\n"]
    for n, (uid, g, t, c, picks, base, y_anyway) in enumerate(cases, 1):
        L.append(f"\n## Learner {n} (uid {uid}), decision point at token {t} of {len(g)}\n")
        hist = g.iloc[:t]
        ex = hist.groupby("exercise_id", sort=False).agg(day=("ts", lambda s: s.iloc[0] / 86400000), session=("session", "first"),
                                                            toks=("question_str", list), resp=("response", list)).tail(8)
        L.append("Last 8 exercises before the decision point (✓ correct, ✗ error):\n")
        for _, e in ex.iterrows():
            L.append(f"- day {e['day']:.2f} [{e['session']}]: " + " ".join(f"{w}{'✓' if r else '✗'}" for w, r in zip(e["toks"], e["resp"])))
        nxt = g.iloc[t]
        L.append(f"\nAbout to do: exercise {nxt['exercise_id']} ({nxt['session']}), first token '{nxt['question_str']}' ({nxt['area']}). "
                 f"Student-model P(correct) = {base:.2f}. What actually happened over the next 5 {nxt['area']} tokens in later exercises: accuracy {y_anyway:.2f}.\n")
        L.append(f"Candidate pool: {len(c)} distinct recent tokens ({(c['action']=='correction').sum()} corrections, {(c['action']=='review').sum()} reviews).\n")
        for name, s in picks.items():
            L.append(f"\n**{name}** picked: " + "; ".join(
                f"'{r.question_str}' ({r.area}, {r.action}, seen ×{r.seen}, last {fmt_gap(r.gap_log)} ago, τ_T={r.tau_t:+.3f} τ_DR={r.tau_dr:+.3f}, e={r.e:.2f}, p_hlr={r.p_hlr:.2f}{', REALIZED' if r.realized else ''})"
                for r in s.itertuples()))
        L.append("")
    path.write_text("\n".join(L))


if __name__ == "__main__":
    main()

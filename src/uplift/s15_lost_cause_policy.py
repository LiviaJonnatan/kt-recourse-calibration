"""What should a student do right after getting a topic wrong? State-aware, spacing-controlled.

Topic   = level-3 KC node on XES3G5M (from questions.json routes), 'area' on SLAM / ASSISTments.
Decision point: an interaction in topic A answered WRONG. State:
    slip   recent same-topic accuracy (pre_area) >= 0.5
    stuck  pre_area < 0.5   (needs >= 3 prior same-topic interactions)
Action = what the student did at the very next interaction (mutually exclusive):
    retry_same        same item again
    stay_easier / stay_matched / stay_harder
                      a different item in topic A, difficulty relative to the student's error rate (+/- 0.10)
    sibling / cousin / unrelated      (XES3G5M only: same level-2 parent / same level-1 / other)
    switch                            (SLAM, ASSISTments: any other area)
Outcome yA: accuracy on the next 5 interactions in topic A occurring AFTER the next interaction
            (so the action's own item never counts), NaN if fewer than 5.
Spacing control: return_gap = log10 seconds from the decision point to the first later interaction
            in A that counts toward yA. Entered in the propensity and reported within gap bins.
Estimates (held-out students):
    IPW mean yA per action x state (multinomial propensity on state covariates + return_gap)
    within-student paired contrasts, restricted to pairs in the same return-gap bin
    policy: outcome model yA ~ (x, return_gap, action) on train; per stuck test event recommend argmax;
            compare observed yA when the logged action matched the recommendation vs not (IPW + paired)
Usage:  python s15_lost_cause_policy.py --out ../out --raw ../../xes/XES3G5M     (XES3G5M)
        python s15_lost_cause_policy.py --out ../out_slam                         (SLAM / ASSISTments)
"""
from __future__ import annotations

import argparse, json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

SEED = 0
XC = ["pre_area", "pre_all", "hist", "n_area", "p_dkt", "difficulty"]
GAP_BINS = [-1, 3.56, 4.94, 99]            # <1h, 1h-1d, >1d (log10 s)
GAP_LAB = ["<1h", "1h-1d", ">1d"]


def build(d: pd.DataFrame, topic_col: str) -> pd.DataFrame:
    d = d.sort_values(["uid", "seq_pos"]).reset_index(drop=True)
    nxt = d.groupby("uid").shift(-1)
    d["n_topic"] = nxt[topic_col]; d["n_q"] = nxt["question"]; d["n_diff"] = nxt["difficulty"]
    for c in ["l1", "l2"]:
        if c in d.columns: d[f"n_{c}"] = nxt[c]
    # yA: next 5 in topic after position t+1; return_gap: time to first counted one (vectorised per group)
    yA = np.full(len(d), np.nan, np.float32); rg = np.full(len(d), np.nan, np.float32)
    for _, g in d.groupby(["uid", topic_col], sort=False, observed=True):
        n = len(g)
        if n < 6: continue
        idx = g.index.to_numpy(); r = g["response"].to_numpy(np.float32); p = g["seq_pos"].to_numpy(); t = g["ts"].to_numpy(np.float64)
        cs = np.concatenate([[0.0], np.cumsum(r)])
        i = np.arange(n); j = i + 1 + (np.r_[p[1:], p[-1] + 2] == p + 1)        # skip row i+1 if it is the immediate next interaction
        ok = j + 5 <= n
        yA[idx[ok]] = (cs[j[ok] + 5] - cs[j[ok]]) / 5.0
        rg[idx[ok]] = np.log10(np.maximum((t[j[ok]] - t[i[ok]]) / 1000.0, 1.0))
    d["yA"] = yA; d["return_gap"] = rg
    m = d[(d["response"] == 0) & d["yA"].notna() & d["n_topic"].notna() & d["pre_area"].notna() & d["p_dkt"].notna() & d["difficulty"].notna()].copy()
    m["state"] = np.where(m["pre_area"] < 0.5, "stuck", "slip")
    err = 1 - m["pre_area"]; rel = m["n_diff"] - err
    same_topic = m["n_topic"] == m[topic_col]
    stay = np.select([rel <= -0.10, rel >= 0.10], ["stay_easier", "stay_harder"], "stay_matched")
    if "l2" in m.columns:
        away = np.select([m["n_l2"] == m["l2"], m["n_l1"] == m["l1"]], ["sibling", "cousin"], "unrelated")
    else:
        away = np.full(len(m), "switch", dtype=object)
    m["action"] = np.where(m["n_q"] == m["question"], "retry_same", np.where(same_topic, stay, away))
    m["gap_bin"] = pd.cut(m["return_gap"], GAP_BINS, labels=GAP_LAB)
    return m


def ipw_table(tr, te, actions):
    prop = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, min_samples_leaf=200, random_state=SEED).fit(
        tr[XC + ["return_gap"]].to_numpy(np.float32), tr["action"])
    P = prop.predict_proba(te[XC + ["return_gap"]].to_numpy(np.float32)); cls = list(prop.classes_)
    e = np.clip(P[np.arange(len(te)), [cls.index(a) for a in te["action"]]], 0.02, 0.98)
    te = te.assign(w=1 / e)
    rows = []
    for st, gs in te.groupby("state"):
        for a_, g in gs.groupby("action"):
            rows.append({"state": st, "action": a_, "n": len(g), "ipw_yA": np.average(g["yA"], weights=g["w"]), "naive_yA": g["yA"].mean(),
                         "mean_return_gap_h": float(10 ** g["return_gap"].mean() / 3600)})
    return te, pd.DataFrame(rows).pivot(index="action", columns="state", values=["n", "ipw_yA"]).reindex(actions)


PAIRED_ROWS = []


def paired(te, a_, b_, rng, label, same_gap=True, state=""):
    key = ["uid", "gap_bin"] if same_gap else ["uid"]
    pv = te.groupby(key + ["action"], observed=True)["yA"].mean().unstack()
    if a_ not in pv.columns or b_ not in pv.columns: return None
    both = pv.dropna(subset=[a_, b_]); diff = (both[a_] - both[b_]).to_numpy()
    if len(diff) < 20: return None
    bs = [rng.choice(diff, len(diff)).mean() for _ in range(1000)]
    PAIRED_ROWS.append({"state": state, "contrast": label, "diff": diff.mean(), "ci_lo": np.percentile(bs, 2.5), "ci_hi": np.percentile(bs, 97.5), "n_pairs": len(both)})
    return f"  {label:28s} {diff.mean():+.3f} [{np.percentile(bs, 2.5):+.3f}, {np.percentile(bs, 97.5):+.3f}]  (n={len(both)} student{'-gapbin' if same_gap else ''} pairs)"


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, required=True); ap.add_argument("--raw", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(); rng = np.random.default_rng(a.seed)
    global SEED; SEED = a.seed
    cols = ["split", "uid", "seq_pos", "question", "area", "response", "ts", "pre_area", "pre_all", "hist", "n_area", "difficulty"]
    d = pd.read_parquet(a.out / "events.parquet", columns=cols)
    p = pd.concat([pd.read_parquet(a.out / f"p_dkt_{s}.parquet") for s in ["train", "test"]])
    d = d.merge(p, on=["uid", "seq_pos"], how="left")
    if a.raw is not None:
        q = json.load(open(a.raw / "metadata/questions.json", encoding="utf-8-sig"))
        route = {int(k): (v.get("kc_routes") or [""])[0].split("----") for k, v in q.items()}
        qs = d["question"].unique()
        for n in (1, 2, 3):
            mp = {int(x): "----".join(route.get(int(x), [""])[:n]) for x in qs}
            d[f"l{n}"] = d["question"].map(mp).astype("category").cat.codes.astype(np.int32)
        topic = "l3"; actions = ["retry_same", "stay_easier", "stay_matched", "stay_harder", "sibling", "cousin", "unrelated"]
    else:
        d["area"] = d["area"].astype(str); topic = "area"; actions = ["retry_same", "stay_easier", "stay_matched", "stay_harder", "switch"]
    m = build(d, topic)
    tr, te = m[m.split == "train"], m[m.split == "test"]
    print(f"decision points (wrong answer, outcome defined): train {len(tr)}, test {len(te)}")
    print("test states:", te["state"].value_counts().to_dict())
    print("test actions:", te["action"].value_counts().to_dict())
    te, tab = ipw_table(tr, te, actions)
    pd.set_option("display.width", 200)
    print("\n== IPW next-5 accuracy on the stuck topic, by action x state (propensity includes return gap):")
    print(tab.round(3).to_string())
    print("\n== Within return-gap bin (stuck students only), IPW yA by action:")
    st = te[te.state == "stuck"]
    print(st.groupby(["gap_bin", "action"], observed=True).apply(lambda g: pd.Series({"n": len(g), "ipw_yA": np.average(g["yA"], weights=g["w"])})).unstack("action")["ipw_yA"].reindex(columns=actions).round(3).to_string())
    print("\n== Paired within-student contrasts, same return-gap bin:")
    for state in ["stuck", "slip"]:
        s = te[te.state == state]; print(f" [{state}]")
        pairs = [("stay_matched", "retry_same", "new same-topic vs retry"), ("stay_easier", "stay_matched", "easier vs matched"), ("stay_easier", "stay_harder", "easier vs harder")]
        pairs += ([("sibling", "stay_matched", "sibling vs stay"), ("unrelated", "stay_matched", "unrelated vs stay"), ("sibling", "unrelated", "sibling vs unrelated"), ("cousin", "unrelated", "cousin vs unrelated")]
                  if "sibling" in actions else [("switch", "stay_matched", "switch vs stay"), ("switch", "retry_same", "switch vs retry")])
        for a_, b_, lab in pairs:
            out = paired(s, a_, b_, rng, lab, state=state); print(out or f"  {lab:28s} (insufficient pairs)")
    # policy for stuck students
    mu = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, min_samples_leaf=200, random_state=SEED)
    A = pd.get_dummies(tr["action"]).reindex(columns=actions, fill_value=0).to_numpy(np.float32)
    mu.fit(np.hstack([tr[XC + ["return_gap"]].to_numpy(np.float32), A]), tr["yA"].to_numpy(np.float32))
    stuck = te[te.state == "stuck"].copy()
    preds = np.stack([mu.predict(np.hstack([stuck[XC + ["return_gap"]].to_numpy(np.float32),
                                            np.tile(np.eye(len(actions))[i], (len(stuck), 1)).astype(np.float32)])) for i in range(len(actions))], 1)
    stuck["rec"] = np.array(actions)[preds.argmax(1)]; stuck["agree"] = stuck["rec"] == stuck["action"]
    print(f"\n== Policy for stuck students: recommended action shares {stuck['rec'].value_counts(normalize=True).round(3).to_dict()}")
    for lab, g in stuck.groupby("agree"):
        print(f"  logged action {'MATCHES' if lab else 'differs from'} recommendation: IPW yA = {np.average(g['yA'], weights=g['w']):.3f} (n={len(g)})")
    pv = stuck.assign(ag=np.where(stuck["agree"], "match", "other")).groupby(["uid", "gap_bin", "ag"], observed=True)["yA"].mean().unstack().dropna()
    if len(pv) > 20:
        diff = (pv["match"] - pv["other"]).to_numpy(); bs = [rng.choice(diff, len(diff)).mean() for _ in range(1000)]
        print(f"  paired within student & gap bin, match - other: {diff.mean():+.3f} [{np.percentile(bs, 2.5):+.3f}, {np.percentile(bs, 97.5):+.3f}] (n={len(pv)})")
        PAIRED_ROWS.append({"state": "stuck", "contrast": "policy match - other", "diff": diff.mean(), "ci_lo": np.percentile(bs, 2.5), "ci_hi": np.percentile(bs, 97.5), "n_pairs": len(pv)})
    tab.to_csv(a.out / f"s15_lost_cause_table_s{a.seed}.csv")
    pd.DataFrame(PAIRED_ROWS).to_csv(a.out / f"s15_lost_cause_paired_s{a.seed}.csv", index=False)
    stuck["rec"].value_counts(normalize=True).to_csv(a.out / f"s15_lost_cause_policy_mix_s{a.seed}.csv")


if __name__ == "__main__":
    main()
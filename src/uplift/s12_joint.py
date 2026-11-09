"""Joint ranker: one effect model over both re-attempt types, with action type as a feature, so
corrections and reviews are scored on the same scale and compared in one ranking; plus a LEARNED
veto threshold (re-attempt only if tau > t*, t* chosen on train to maximise policy value) instead
of the fixed tau_LCB <= 0 rule.

    mu_new(x)            control outcome model (shared covariates)
    mu_re(x, g, a)       treated outcome model, a = 1[correction]
    tau(x, g, a) = mu_re - mu_new ; tau_lcb = tau - sd over B student-bootstrap refits

Evaluation (held-out):
  1. Per-arm top-20% gain of the joint model vs the separate-arm models (same events).
  2. Pooled ranking over both arms: top-20% gain when corrections and reviews compete.
  3. Veto: policy value (IPW) of "re-attempt if tau_lcb > t*" with t* learned on train, vs t* = 0,
     per arm.

Usage: python s12_joint.py --out ../../out/slam --tag _s0 [--outcome y_item] [--extra p_hlr] [--boot 20]
Reads events.parquet + p_dkt_*.parquet; writes s12_joint<tag>.csv.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import s3_uplift
from s3_uplift import SHARED, TREATED_EXTRA, hgb_clf, hgb_reg, load_events
from metrics import ipw_weights, uplift_at_k

ARMS = ["correction", "review"]


def fit_joint(d: pd.DataFrame, B: int, rng, extra: list[str]):
    d = d.copy(); d["is_corr"] = (d["action"] == "correction").astype(np.float32)
    T = (d["action"] != "new").astype(int).to_numpy(); y = d["y_next"].to_numpy(np.float32)
    X0 = d[SHARED].to_numpy(np.float32); X1 = d[SHARED + extra + ["is_corr"]].to_numpy(np.float32)
    m0 = hgb_reg().fit(X0[T == 0], y[T == 0]); m1 = hgb_reg().fit(X1[T == 1], y[T == 1])
    prop = hgb_clf().fit(X0, d["action"].to_numpy())           # multinomial new/correction/review
    uids = d["uid"].to_numpy(); uu = np.unique(uids); boots = []
    for _ in range(B):
        cnt = pd.Series(rng.choice(uu, len(uu), replace=True)).value_counts()
        w = pd.Series(uids).map(cnt).fillna(0).to_numpy(np.float32)
        b0 = hgb_reg().fit(X0[(T == 0) & (w > 0)], y[(T == 0) & (w > 0)], sample_weight=w[(T == 0) & (w > 0)])
        b1 = hgb_reg().fit(X1[(T == 1) & (w > 0)], y[(T == 1) & (w > 0)], sample_weight=w[(T == 1) & (w > 0)])
        boots.append((b0, b1))
    return dict(m0=m0, m1=m1, prop=prop, boots=boots, extra=extra)


def score_joint(M, d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy(); d["is_corr"] = (d["action"] == "correction").astype(np.float32)
    X0 = d[SHARED].to_numpy(np.float32); X1 = d[SHARED + M["extra"] + ["is_corr"]].to_numpy(np.float32)
    mu0 = M["m0"].predict(X0); mu1 = M["m1"].predict(X1); tau = mu1 - mu0
    bs = np.stack([b1.predict(X1) - b0.predict(X0) for b0, b1 in M["boots"]])
    P = M["prop"].predict_proba(X0); cls = list(M["prop"].classes_)
    e_act = np.where(d["action"] == "correction", P[:, cls.index("correction")],
                     np.where(d["action"] == "review", P[:, cls.index("review")], P[:, cls.index("new")]))
    return pd.DataFrame({"mu0": mu0, "mu1": mu1, "tau_j": tau, "tau_j_lcb": tau - bs.std(0), "e_act": e_act,
                         "e_new": P[:, cls.index("new")]}, index=d.index)


def policy_value(tr: pd.DataFrame, ct: pd.DataFrame, thr: float) -> float:
    """IPW value of 're-attempt if tau_j_lcb > thr else new item in same area' on treated events."""
    w_ct = 1 / np.clip(ct["e_new"].to_numpy(), 0.01, 0.99)
    ctrl_area = ct.assign(w=w_ct).groupby("area", observed=True).apply(lambda g: np.average(g["y_next"], weights=g["w"])).to_dict()
    y_ct = tr["area"].map(ctrl_area).to_numpy(float); ok = ~np.isnan(y_ct)
    w = 1 / np.clip(tr["e_act"].to_numpy(), 0.01, 0.99)
    rec = tr["tau_j_lcb"].to_numpy() > thr
    return float(np.average(np.where(rec, tr["y_next"].to_numpy(), y_ct)[ok], weights=w[ok]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True); ap.add_argument("--tag", default="")
    ap.add_argument("--outcome", default="y_next"); ap.add_argument("--extra", default="")
    ap.add_argument("--ctrl_cap", type=int, default=400000); ap.add_argument("--treat_cap", type=int, default=300000)
    ap.add_argument("--boot", type=int, default=8); ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    extra = list(TREATED_EXTRA) + [c for c in a.extra.split(",") if c and c not in TREATED_EXTRA]
    s3_uplift.OUTCOME = a.outcome; rng = np.random.default_rng(a.seed)
    train = load_events(a.out, "train", a.ctrl_cap, rng)
    parts = [train[train.action == "new"]] + [train[train.action == arm].sample(min(a.treat_cap, (train.action == arm).sum()), random_state=1) for arm in ARMS]
    train = pd.concat(parts).reset_index(drop=True)
    test = load_events(a.out, "test", None, rng)
    for c in extra:
        train[c] = train[c].fillna(0.0); test[c] = test[c].fillna(0.0)
    M = fit_joint(train, a.boot, rng, extra)
    rows = []
    # per-arm and pooled evaluation
    sc_te = score_joint(M, test); test = pd.concat([test, sc_te], axis=1)
    sep = {arm: pd.read_parquet(a.out / f"scored_test_{arm}{a.tag}.parquet")[["uid", "seq_pos", "tau_t", "tau_sd"]] for arm in ARMS}
    pooled = []
    for arm in ARMS:
        tr = test[test.action == arm]; ct = test[test.action == "new"]
        need = tr["area"].value_counts() * 5
        ct = pd.concat([g.sample(min(len(g), int(need.get(k, 0))), random_state=1) for k, g in ct.groupby("area", observed=True) if need.get(k, 0) > 0])
        e = pd.concat([tr, ct]).merge(sep[arm], on=["uid", "seq_pos"], how="left")
        y = e["y_next"].to_numpy(float); t = (e.action == arm).to_numpy(int)
        rows.append({"eval": f"{arm}: joint vs separate", "joint_lcb": uplift_at_k(y, t, e["tau_j_lcb"].to_numpy(), frac=.2),
                     "separate_lcb": uplift_at_k(y, t, (e["tau_t"] - e["tau_sd"]).fillna(-9).to_numpy(), frac=.2),
                     "p_dkt": uplift_at_k(y, t, e["p_dkt"].to_numpy(), frac=.2), "n_treated": int(t.sum())})
        pooled.append(e)
    e = pd.concat(pooled); y = e["y_next"].to_numpy(float); t = (e.action != "new").to_numpy(int)
    top = e.iloc[np.argsort(-e["tau_j_lcb"].to_numpy())[: int(.2 * len(e))]]
    rows.append({"eval": "pooled (both arms compete)", "joint_lcb": uplift_at_k(y, t, e["tau_j_lcb"].to_numpy(), frac=.2),
                 "p_dkt": uplift_at_k(y, t, e["p_dkt"].to_numpy(), frac=.2), "n_treated": int(t.sum()),
                 "share_corrections_in_top20": float((top.action == "correction").sum() / max((top.action != "new").sum(), 1))})
    # learned veto threshold on train
    sc_tr = score_joint(M, train); train = pd.concat([train, sc_tr], axis=1)
    for arm in ARMS:
        tr_tr = train[train.action == arm]; ct_tr = train[train.action == "new"]
        grid = np.quantile(tr_tr["tau_j_lcb"], np.linspace(0.02, 0.98, 25))
        vals = [policy_value(tr_tr, ct_tr, g) for g in grid]; t_star = float(grid[int(np.argmax(vals))])
        tr_te = test[test.action == arm]; ct_te = test[test.action == "new"]
        v_always = policy_value(tr_te, ct_te, -9); v_zero = policy_value(tr_te, ct_te, 0.0); v_star = policy_value(tr_te, ct_te, t_star)
        rows.append({"eval": f"{arm}: veto", "t_star": t_star, "share_vetoed_at_t_star": float((tr_te["tau_j_lcb"] <= t_star).mean()),
                     "value_always": v_always, "value_thr0": v_zero, "value_learned": v_star,
                     "gain_thr0": v_zero - v_always, "gain_learned": v_star - v_always})
    r = pd.DataFrame(rows); pd.set_option("display.width", 220); print(r.round(3).to_string(index=False))
    r.to_csv(a.out / f"s12_joint{a.tag}.csv", index=False)


if __name__ == "__main__":
    main()
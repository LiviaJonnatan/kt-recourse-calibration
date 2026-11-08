"""Stage 3 - uplift (CATE) model for re-attempt actions.

Estimand, per treatment arm a in {correction, review}:
    tau_a(x) = E[y_next | do(a), x] - E[y_next | do(new), x]
    i.e. the lift in next-5 same-area accuracy from re-attempting a past question
    now, compared with attempting a new question in the same area, for a student
    with covariates x.

Covariates
    shared (used by propensity and both arms): pre_area, pre_all, hist, n_area,
        difficulty, single, p_dkt
    treated-arm only (known at recommendation time for a candidate): gap_log,
        n_attempt

Learners (all scikit-learn HistGradientBoosting, cross-fitted by student fold)
    propensity  e_a(x) = P(action = a | x)         multinomial over {new, correction, review}
    T-learner   tau_T  = mu_a(x, g) - mu_new(x)
    X-learner   tau_X  = e-weighted blend of imputed effects (Kunzel et al. 2019)
    DR-learner  tau_DR = regression of the doubly-robust pseudo-outcome on x (Kennedy 2023)
    bootstrap   B refits of the T-learner on student-resampled data -> sd(tau) for the LCB

Outputs
    ../out/uplift_<arm>.pkl         fitted models (pickle)
    ../out/scored_test_<arm>.parquet test events of arm `a` and matched controls with every score
"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

SHARED = ["pre_area", "pre_all", "hist", "n_area", "difficulty", "single", "p_dkt"]
TREATED_EXTRA = ["gap_log", "n_attempt"]
ARMS = ["correction", "review"]
SEED = 2026


def hgb_reg(**kw):
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                         min_samples_leaf=200, l2_regularization=1.0, random_state=SEED, **kw)


def hgb_clf():
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                          min_samples_leaf=200, l2_regularization=1.0, random_state=SEED)


OUTCOME = "y_next"


def load_events(out: Path, split: str, ctrl_cap: int | None, rng) -> pd.DataFrame:
    d = pd.read_parquet(out / "events.parquet")
    if OUTCOME != "y_next":
        d["y_next"] = d[OUTCOME]
    d = d[d["split"] == split]
    p = pd.read_parquet(out / f"p_dkt_{split}.parquet")
    d = d.merge(p, on=["uid", "seq_pos"], how="left")
    d = d[d["y_next"].notna() & d["pre_area"].notna() & d["p_dkt"].notna() & d["difficulty"].notna()]
    for c in TREATED_EXTRA:
        if c in d.columns:
            d[c] = d[c].fillna(0.0)
    if ctrl_cap is not None:
        ctrl = d[d["action"] == "new"]
        if len(ctrl) > ctrl_cap:
            ctrl = ctrl.sample(ctrl_cap, random_state=rng.integers(1 << 31))
        d = pd.concat([d[d["action"] != "new"], ctrl])
    return d.reset_index(drop=True)


class Uplift:
    """All learners for one arm, with K-fold cross-fitting by student."""

    def __init__(self, arm: str, k: int = 2):
        self.arm, self.k = arm, k
        self.models: dict = {}
        self.shared, self.extra = list(SHARED), list(TREATED_EXTRA)   # frozen feature lists

    def _fold(self, uid: np.ndarray) -> np.ndarray:
        return (pd.util.hash_array(uid.astype(np.int64)) % self.k).astype(int)

    def fit(self, d: pd.DataFrame, B: int = 8, rng=None) -> "Uplift":
        d = d[d["action"].isin(["new", self.arm])].copy()
        T = (d["action"] == self.arm).astype(int).to_numpy()
        y = d["y_next"].to_numpy(np.float32)
        X0 = d[SHARED].to_numpy(np.float32)
        X1 = d[SHARED + TREATED_EXTRA].to_numpy(np.float32)
        fold = self._fold(d["uid"].to_numpy())
        n = len(d)
        e_hat = np.zeros(n, np.float32); mu0 = np.zeros(n, np.float32); mu1 = np.zeros(n, np.float32)
        self.models["prop"], self.models["mu0"], self.models["mu1"] = [], [], []
        for f in range(self.k):
            tr, te = fold != f, fold == f
            prop = hgb_clf().fit(X0[tr], T[tr]); self.models["prop"].append(prop)
            e_hat[te] = prop.predict_proba(X0[te])[:, 1]
            m0 = hgb_reg().fit(X0[tr & (T == 0)], y[tr & (T == 0)]); self.models["mu0"].append(m0)
            m1 = hgb_reg().fit(X1[tr & (T == 1)], y[tr & (T == 1)]); self.models["mu1"].append(m1)
            mu0[te] = m0.predict(X0[te]); mu1[te] = m1.predict(X1[te])
        e_hat = np.clip(e_hat, 0.005, 0.995)
        # DR pseudo-outcome -> tau_DR(x) uses shared + treated extras (extras are candidate properties)
        phi = mu1 - mu0 + T * (y - mu1) / e_hat - (1 - T) * (y - mu0) / (1 - e_hat)
        self.models["dr"] = hgb_reg().fit(X1, phi)
        # X-learner: imputed effects, two regressions, e-weighted blend
        d1 = y[T == 1] - mu0[T == 1]; d0 = mu1[T == 0] - y[T == 0]
        self.models["x1"] = hgb_reg().fit(X1[T == 1], d1)
        self.models["x0"] = hgb_reg().fit(X1[T == 0], d0)
        # bootstrap T-learner for uncertainty (student-level resampling)
        self.models["boot"] = []
        uids = d["uid"].to_numpy(); uu = np.unique(uids)
        for b in range(B):
            samp = rng.choice(uu, len(uu), replace=True)
            cnt = pd.Series(samp).value_counts()
            w = pd.Series(uids).map(cnt).fillna(0).to_numpy(np.float32)
            m0 = hgb_reg().fit(X0[(T == 0) & (w > 0)], y[(T == 0) & (w > 0)], sample_weight=w[(T == 0) & (w > 0)])
            m1 = hgb_reg().fit(X1[(T == 1) & (w > 0)], y[(T == 1) & (w > 0)], sample_weight=w[(T == 1) & (w > 0)])
            self.models["boot"].append((m0, m1))
        self.train_stats = dict(n=int(n), n_treated=int(T.sum()), ate_naive=float(y[T == 1].mean() - y[T == 0].mean()),
                                ate_dr=float(phi.mean()), e_mean_treated=float(e_hat[T == 1].mean()))
        return self

    def score(self, d: pd.DataFrame) -> pd.DataFrame:
        sh = getattr(self, "shared", SHARED); ex = getattr(self, "extra", TREATED_EXTRA)
        X0 = d[sh].to_numpy(np.float32); X1 = d[sh + ex].to_numpy(np.float32)
        e = np.mean([m.predict_proba(X0)[:, 1] for m in self.models["prop"]], axis=0)
        mu0 = np.mean([m.predict(X0) for m in self.models["mu0"]], axis=0)
        mu1 = np.mean([m.predict(X1) for m in self.models["mu1"]], axis=0)
        tau_t = mu1 - mu0
        tau_x = e * self.models["x0"].predict(X1) + (1 - e) * self.models["x1"].predict(X1)
        tau_dr = self.models["dr"].predict(X1)
        boots = np.stack([m1.predict(X1) - m0.predict(X0) for m0, m1 in self.models["boot"]])
        out = pd.DataFrame({"e": e, "mu0": mu0, "mu1": mu1, "tau_t": tau_t, "tau_x": tau_x, "tau_dr": tau_dr,
                            "tau_sd": boots.std(0)}, index=d.index)
        return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ctrl_cap", type=int, default=400_000, help="controls subsampled for training")
    ap.add_argument("--boot", type=int, default=8)
    ap.add_argument("--treat_cap", type=int, default=None, help="treated events subsampled per arm for training")
    ap.add_argument("--extra", default="", help="comma-separated extra treated-arm covariates, e.g. p_hlr")
    ap.add_argument("--outcome", default="y_next", help="outcome column: y_next | y_item | y_area20")
    ap.add_argument("--tag", default="", help="suffix for output files")
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    global SEED
    SEED = a.seed
    a.tag = f"{a.tag}_s{a.seed}"
    if a.extra:
        TREATED_EXTRA.extend([c for c in a.extra.split(",") if c not in TREATED_EXTRA])
    rng = np.random.default_rng(SEED)
    global OUTCOME
    OUTCOME = a.outcome
    train = load_events(a.out, "train", a.ctrl_cap, rng)
    if a.treat_cap:
        parts = [train[train["action"] == "new"]]
        for arm in ARMS:
            t = train[train["action"] == arm]
            parts.append(t.sample(min(len(t), a.treat_cap), random_state=1))
        train = pd.concat(parts).reset_index(drop=True)
    test = load_events(a.out, "test", None, rng)
    print(f"train events {len(train)} ({train['action'].value_counts().to_dict()}); test events {len(test)}")
    for arm in ARMS:
        up = Uplift(arm).fit(train, B=a.boot, rng=rng)
        print(arm, up.train_stats)
        pickle.dump(up, open(a.out / f"uplift_{arm}{a.tag}.pkl", "wb"))
        te = test[test["action"].isin(["new", arm])]
        sc = up.score(te)
        te = pd.concat([te, sc], axis=1)
        te.to_parquet(a.out / f"scored_test_{arm}{a.tag}.parquet", index=False)


if __name__ == "__main__":
    main()

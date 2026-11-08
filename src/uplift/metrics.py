"""Evaluation metrics for ranking signals and chosen sets.

Qini / uplift AUC follow Radcliffe (2007) and Radcliffe & Surry (2011): sort units by
score (descending), walk down the list, and at each depth compute
    g(phi) = sum_treated(y) - sum_control(y) * (n_treated / n_control)
Area under the Qini curve, minus the random (straight-line) area, normalised by the
random-targeting area so that 0 = random and the number is comparable across arms:
    qini_coef = (AUQ - AUQ_random) / |AUQ_random| ... we report AUQ_norm = AUQ / (n_treated * ATE)
plus the raw Qini coefficient (AUQ - area of the diagonal). An IPW variant reweights
each unit by 1/e or 1/(1-e) so the curve is a debiased estimate under confounding.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def qini_curve(y: np.ndarray, t: np.ndarray, score: np.ndarray, w: np.ndarray | None = None, n_points: int = 101):
    """Returns depth phi in [0,1] and cumulative incremental gain g(phi), both arrays."""
    if w is None:
        w = np.ones(len(y))
    o = np.argsort(-score, kind="stable")
    y, t, w = y[o], t[o], w[o]
    wt, wc = w * t, w * (1 - t)
    cum_t = np.cumsum(wt * y); cum_c = np.cumsum(wc * y)
    n_t = np.cumsum(wt); n_c = np.cumsum(wc)
    with np.errstate(divide="ignore", invalid="ignore"):
        g = cum_t - cum_c * np.where(n_c > 0, n_t / n_c, 0.0)
    idx = np.unique(np.linspace(0, len(y) - 1, n_points).astype(int))
    return idx / (len(y) - 1), g[idx]


def qini_coefficient(y, t, score, w=None) -> dict:
    phi, g = qini_curve(y, t, score, w, n_points=201)
    area = np.trapezoid(g, phi)
    diag = 0.5 * g[-1]                     # random targeting: straight line from 0 to total gain
    n_t = (t * (w if w is not None else 1)).sum()
    return {"auq": float(area), "qini": float(area - diag), "total_gain": float(g[-1]),
            "qini_norm": float((area - diag) / max(abs(diag), 1e-9)), "n_treated": float(n_t)}


def uplift_at_k(y, t, score, w=None, frac: float = 0.2) -> float:
    """Observed treated-minus-control outcome in the top `frac` of the ranking."""
    if w is None:
        w = np.ones(len(y))
    o = np.argsort(-score, kind="stable")[: max(1, int(frac * len(y)))]
    yy, tt, ww = y[o], t[o], w[o]
    mt = (ww * tt).sum(); mc = (ww * (1 - tt)).sum()
    if mt == 0 or mc == 0:
        return np.nan
    return float((ww * tt * yy).sum() / mt - (ww * (1 - tt) * yy).sum() / mc)


def ipw_weights(t: np.ndarray, e: np.ndarray, clip=(0.01, 0.99)) -> np.ndarray:
    e = np.clip(e, *clip)
    return np.where(t == 1, 1 / e, 1 / (1 - e))


def four_groups(mu0: np.ndarray, mu1: np.ndarray, hi: float = 0.8, lo: float = 0.2) -> pd.Series:
    """Marketing-style breakdown of candidates by (mu0, mu1): sure things (both high),
    lost causes (both low), persuadables (mu1 - mu0 large and mu0 low/mid), sleeping dogs (mu1 < mu0)."""
    tau = mu1 - mu0
    lab = np.full(len(mu0), "other", dtype=object)
    lab[(mu0 >= hi) & (mu1 >= hi)] = "sure_thing"
    lab[(mu0 < lo) & (mu1 < lo)] = "lost_cause"
    lab[(tau > 0.05) & (mu0 < hi)] = "persuadable"
    lab[tau < -0.05] = "sleeping_dog"
    return pd.Series(lab).value_counts(normalize=True)


def dr_set_value(tau_dr: np.ndarray, e: np.ndarray, support_min: float = 0.02) -> dict:
    """Model-based value of a chosen set with a support filter: mean DR-CATE over
    evaluable actions (propensity >= support_min), plus the evaluability rate."""
    ok = e >= support_min
    return {"evaluability": float(ok.mean()) if len(ok) else np.nan,
            "mean_tau_dr_supported": float(tau_dr[ok].mean()) if ok.any() else np.nan,
            "mean_tau_dr_all": float(tau_dr.mean()) if len(tau_dr) else np.nan}

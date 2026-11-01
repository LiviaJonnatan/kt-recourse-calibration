"""RQ2: observed effects of cross-batch re-attempts in XES3G5M.

Run from the repo root after reconstruct.py, difficulty.py and prevalence_tables.py:
    uv run python src/audit/observed_effects.py 2>&1 | tee docs/exploration/$(date +%F)_rq2_observed_effects.log

Reads   data/processed/xes3g5m_clean.parquet
        data/processed/item_difficulty.csv
        data/raw/XES3G5M/metadata/questions.json
Writes  data/processed/rq2/<table>.csv and prints each as markdown.

Options:
    --kc_level N    KC unit for the H2c windows and matching: the first N components of the question's
                    first kc_routes entry in questions.json (1 = coarsest). Default: the leaf KC id
                    (first_kc), the original definition; see kc_level_check.py for why a coarser
                    level is needed on XES3G5M.
    --chance {n,n-1}  chance baseline for single-choice corrections: 1/n options (default) or
                    1/(n-1), treating the first wrong option as eliminated on the retry.

Analyses (definitions as in prevalence_tables.py; question type and the chance correction were
added after the RQ1 tables showed repeats concentrate on single-choice items):
  H2a  correction success and review retention by gap class, difficulty tercile and question type,
       with 95% cluster-bootstrap CIs (cluster = student, B = BOOT resamples, seed 2026).
       For single-choice items, correction success is also reported net of chance,
       (p - c) / (1 - c) with c = 1 / number of options for that question.
  H2b  review retention regressed on log(gap in seconds): logistic slope with a cluster-bootstrap CI.
  H2c  matched comparison. Each repeat event (treated) is matched without replacement to one first
       attempt on the same KC by a student who never re-attempted that question (control), on
       split, first KC, history length at the first attempt (+/- 20%), prior same-KC accuracy
       (+/- 0.10) and correctness of the first attempt. Outcome = accuracy on the next 10 same-KC
       interactions after the event (after the repeat for treated, after the first attempt for
       controls; the repeated question itself is excluded) minus accuracy on the 10 same-KC
       interactions before the first attempt. Events without 10 on each side are dropped and
       counted; unmatched events are dropped and counted. If fewer than 30% of eligible events
       match, tolerances are widened once (+/- 40%, +/- 0.15) and this is flagged in the log.

Definitional choices, recorded here:
  - KC = first_kc (the first concept listed for multi-KC questions), or the --kc_level ancestor of the
    question's first kc_route; the level used is written into every H2c output file name.
  - History length at the event = seq_pos of the first attempt, for both treated and control.
  - Prior same-KC accuracy = accuracy over the 10-interaction pre-window (so it is defined exactly
    when the pre-window is).
  - A control student may have re-attempted other questions; only the matched question is required
    to be un-repeated.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

IN = Path("data/processed/xes3g5m_clean.parquet")
DIFF = Path("data/processed/item_difficulty.csv")
QJSON = Path("data/raw/XES3G5M/metadata/questions.json")
OUT = Path("data/processed/rq2")
OUT.mkdir(parents=True, exist_ok=True)

import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--kc_level", type=int, default=None, help="kc_routes depth for H2c; default leaf first_kc")
_ap.add_argument("--chance", choices=["n", "n-1"], default="n")
ARGS = _ap.parse_args()
KC_TAG = f"kclevel{ARGS.kc_level}" if ARGS.kc_level else "leafkc"

SEED = 2026
BOOT = 1000
WINDOW = 10
TOL = dict(hist=0.20, prior=0.10)
TOL_WIDE = dict(hist=0.40, prior=0.15)
TYPE_MAP = {"填空": "fill-in", "单选": "single-choice", "选择": "choice"}
rng = np.random.default_rng(SEED)


# ----------------------------------------------------------------------------- loading
def load() -> pd.DataFrame:
    cols = ["split", "uid", "question", "response", "ts", "seq_pos", "attempt", "is_repeat",
            "prev_seq_pos", "gap_s", "gap_class", "kind", "first_kc"]
    df = pd.read_parquet(IN, columns=cols)
    df = df.merge(pd.read_csv(DIFF, usecols=["question", "tercile"]), on="question", how="left")
    df["tercile"] = df["tercile"].fillna("no tercile")
    with open(QJSON, encoding="utf-8") as f:
        qmeta = json.load(f)
    df["qtype"] = df["question"].map({int(k): TYPE_MAP.get(v.get("type"), "unknown") for k, v in qmeta.items()}).fillna("unknown")
    n_opt = {int(k): len(v["options"]) for k, v in qmeta.items() if isinstance(v.get("options"), dict) and v["options"]}
    denom = df["question"].map(n_opt).astype(float)
    if ARGS.chance == "n-1":
        denom = (denom - 1).clip(lower=1)
    df["chance"] = np.where(df["qtype"] == "single-choice", 1.0 / denom, 0.0)
    # KC unit for H2c
    if ARGS.kc_level:
        routes = {int(k): "----".join((v.get("kc_routes") or [""])[0].split("----")[:ARGS.kc_level]) for k, v in qmeta.items()}
        df["kc"] = df["question"].map(routes).fillna(df["first_kc"].astype(str))
    else:
        df["kc"] = df["first_kc"].astype(str)
    return df


# ----------------------------------------------------------------------------- bootstrap helpers
def cluster_boot_mean(y: np.ndarray, uid: np.ndarray, B: int = BOOT) -> tuple[float, float, float]:
    """Mean of y with a percentile CI from resampling students (clusters) with replacement."""
    u, inv = np.unique(uid, return_inverse=True)
    s = np.bincount(inv, weights=y, minlength=len(u))
    n = np.bincount(inv, minlength=len(u)).astype(float)
    est = s.sum() / n.sum()
    w = rng.multinomial(len(u), np.full(len(u), 1 / len(u)), size=B)      # B x clusters
    boots = (w @ s) / (w @ n)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(est), float(lo), float(hi)


def rate_table(d: pd.DataFrame, strata: list[str], label: str) -> pd.DataFrame:
    rows = []
    for key, g in d.groupby(strata, observed=True):
        key = key if isinstance(key, tuple) else (key,)
        est, lo, hi = cluster_boot_mean(g["response"].to_numpy(float), g["uid"].to_numpy())
        row = dict(zip(strata, key))
        row.update(n_events=len(g), n_students=g["uid"].nunique(), rate=est, ci_lo=lo, ci_hi=hi)
        if label == "correction" and (g["chance"] > 0).all():
            c = g["chance"].to_numpy()
            ok = c < 1                                   # two-option items under n-1 have chance 1
            if ok.any():
                adj = (g["response"].to_numpy(float)[ok] - c[ok]) / (1 - c[ok])
                a_est, a_lo, a_hi = cluster_boot_mean(adj, g["uid"].to_numpy()[ok])
                row.update(net_of_chance=a_est, net_ci_lo=a_lo, net_ci_hi=a_hi,
                           n_net=int(ok.sum()), n_net_excluded=int((~ok).sum()))
        rows.append(row)
    return pd.DataFrame(rows)


def logit_slope(y: np.ndarray, x: np.ndarray, uid: np.ndarray, B: int = 500) -> dict:
    """Logistic regression of y on x (2 params, Newton), slope CI by cluster bootstrap."""
    X = np.column_stack([np.ones_like(x), x])

    def fit(Xm, ym, w=None):
        b = np.zeros(2)
        w = np.ones(len(ym)) if w is None else w
        for _ in range(25):
            p = 1 / (1 + np.exp(-Xm @ b))
            g = Xm.T @ (w * (ym - p))
            H = (Xm * (w * p * (1 - p))[:, None]).T @ Xm
            step = np.linalg.solve(H, g)
            b += step
            if np.abs(step).max() < 1e-8:
                break
        return b

    b0 = fit(X, y)
    u, inv = np.unique(uid, return_inverse=True)
    slopes = []
    for _ in range(B):
        w_cluster = rng.multinomial(len(u), np.full(len(u), 1 / len(u)))
        w = w_cluster[inv].astype(float)
        if w.sum() == 0:
            continue
        slopes.append(fit(X, y, w)[1])
    lo, hi = np.percentile(slopes, [2.5, 97.5])
    return dict(intercept=float(b0[0]), slope_per_log_s=float(b0[1]), ci_lo=float(lo), ci_hi=float(hi),
                odds_ratio_per_10x_gap=float(np.exp(b0[1] * np.log(10))), n=len(y), students=len(u))


# ----------------------------------------------------------------------------- same-KC windows
def kc_windows(df: pd.DataFrame) -> pd.DataFrame:
    """Pre/post WINDOW-interaction same-KC accuracy around every interaction, vectorised.
    post ignores the same-question exclusion; treated events are corrected in h2c()."""
    d = df.sort_values(["uid", "kc", "seq_pos"]).reset_index(drop=True)
    g = d.groupby(["uid", "kc"], sort=False)
    d["kc_rank"] = g.cumcount()
    d["kc_n"] = g["seq_pos"].transform("size")
    c = g["response"].cumsum() - d["response"]                     # correct answers strictly before this row
    c_prev = c.groupby([d["uid"], d["kc"]]).shift(WINDOW)    # value WINDOW rows earlier
    d["pre_acc"] = np.where(d["kc_rank"] >= WINDOW, (c - c_prev.fillna(0)) / WINDOW, np.nan)
    c_after = c + d["response"]                                    # correct answers up to and including this row
    c_fwd = c_after.groupby([d["uid"], d["kc"]]).shift(-WINDOW)
    d["post_acc"] = np.where(d["kc_rank"] + WINDOW < d["kc_n"], (c_fwd - c_after) / WINDOW, np.nan)
    return d


def treated_post_acc(events: pd.DataFrame, d: pd.DataFrame) -> np.ndarray:
    """Post-window for treated events: next WINDOW same-KC interactions after the repeat,
    excluding further attempts at the repeated question."""
    seqs = {k: (g["seq_pos"].to_numpy(), g["question"].to_numpy(), g["response"].to_numpy())
            for k, g in d.groupby(["uid", "kc"], sort=False)}
    out = np.full(len(events), np.nan)
    for i, (uid, kc, pos, q) in enumerate(zip(events["uid"], events["kc"], events["seq_pos"], events["question"])):
        sp, qq, rr = seqs[(uid, kc)]
        j = np.searchsorted(sp, pos, side="right")
        keep = qq[j:] != q
        r = rr[j:][keep]
        if len(r) >= WINDOW:
            out[i] = r[:WINDOW].mean()
    return out


# ----------------------------------------------------------------------------- H2c matching
def match(treated: pd.DataFrame, controls: pd.DataFrame, tol: dict) -> pd.DataFrame:
    """Greedy 1:1 nearest-neighbour matching without replacement within exact strata."""
    pairs = []
    strata = ["split", "kc", "first_response"]
    ctrl_groups = {k: g for k, g in controls.groupby(strata, sort=False)}
    for key, tg in treated.groupby(strata, sort=False):
        if key not in ctrl_groups:
            continue
        cg = ctrl_groups[key].sort_values("hist")
        ch = cg["hist"].to_numpy(float)
        cp = cg["pre_acc"].to_numpy(float)
        cidx = cg.index.to_numpy()
        used = np.zeros(len(cg), bool)
        order = rng.permutation(len(tg))
        th = tg["hist"].to_numpy(float)
        tp = tg["pre_acc"].to_numpy(float)
        tidx = tg.index.to_numpy()
        for i in order:
            lo = np.searchsorted(ch, th[i] * (1 - tol["hist"]), side="left")
            hi = np.searchsorted(ch, th[i] * (1 + tol["hist"]), side="right")
            if hi <= lo:
                continue
            ok = (~used[lo:hi]) & (np.abs(cp[lo:hi] - tp[i]) <= tol["prior"])
            if not ok.any():
                continue
            cand = np.flatnonzero(ok) + lo
            dist = np.abs(ch[cand] - th[i]) / max(th[i], 1) / tol["hist"] + np.abs(cp[cand] - tp[i]) / tol["prior"]
            j = cand[np.argmin(dist)]
            used[j] = True
            pairs.append((tidx[i], cidx[j]))
    return pd.DataFrame(pairs, columns=["treated_idx", "control_idx"])


def h2c(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d = kc_windows(df)
    first = d[d["attempt"] == 0].copy()
    first["first_response"] = first["response"]

    # treated: repeat events, joined to their first attempt's pre-window and history length
    rep = d[d["is_repeat"]].copy()
    fa = first.set_index(["uid", "question"])[["pre_acc", "seq_pos", "first_response"]]
    rep = rep.join(fa.rename(columns={"pre_acc": "pre_acc_first", "seq_pos": "hist"}), on=["uid", "question"])
    rep["pre_acc"] = rep["pre_acc_first"]
    rep["post_acc_treated"] = treated_post_acc(rep, d)
    log = dict(repeat_events=len(rep))
    rep = rep[rep["pre_acc"].notna() & rep["post_acc_treated"].notna()]
    log["eligible_treated_with_both_windows"] = len(rep)

    # controls: first attempts never re-attempted, with both windows
    repeated_q = set(zip(rep["uid"], rep["question"]))
    first["hist"] = first["seq_pos"]
    ctrl = first[first["pre_acc"].notna() & first["post_acc"].notna()]
    ctrl = ctrl[[(u, q) not in repeated_q for u, q in zip(ctrl["uid"], ctrl["question"])]]
    log["control_pool"] = len(ctrl)

    pairs = match(rep, ctrl, TOL)
    log["matched"] = len(pairs)
    log["matched_share"] = len(pairs) / max(len(rep), 1)
    log["tolerance"] = "±20% hist, ±0.10 prior"
    if log["matched_share"] < 0.30:
        pairs = match(rep, ctrl, TOL_WIDE)
        log.update(matched=len(pairs), matched_share=len(pairs) / max(len(rep), 1),
                   tolerance="WIDENED to ±40% hist, ±0.15 prior (section 7 contingency)")

    t = rep.loc[pairs["treated_idx"]]
    c = ctrl.loc[pairs["control_idx"]]
    diff_t = (t["post_acc_treated"] - t["pre_acc"]).to_numpy()
    diff_c = (c["post_acc"] - c["pre_acc"]).to_numpy()
    rows = []
    for name, sel in [("all", np.ones(len(t), bool))] + [(f"kind={k}", (t["kind"] == k).to_numpy()) for k in ["correction", "review"]] \
            + [(f"qtype={q}", (t["qtype"] == q).to_numpy()) for q in t["qtype"].unique()] \
            + [(f"tercile={x}", (t["tercile"] == x).to_numpy()) for x in ["easy", "medium", "hard"]] \
            + [(f"gap={g}", (t["gap_class"].astype(str) == g).to_numpy()) for g in ["<1h", "<1d", "<7d", "7d+"]]:
        if sel.sum() == 0:
            continue
        uid = t["uid"].to_numpy()[sel]
        te, tlo, thi = cluster_boot_mean(diff_t[sel], uid)
        ce, clo, chi = cluster_boot_mean(diff_c[sel], uid)       # paired: resample by treated student
        de, dlo, dhi = cluster_boot_mean(diff_t[sel] - diff_c[sel], uid)
        rows.append(dict(subset=name, n_pairs=int(sel.sum()), treated_change=te, treated_ci=f"[{tlo:.3f}, {thi:.3f}]",
                         control_change=ce, control_ci=f"[{clo:.3f}, {chi:.3f}]",
                         matched_difference=de, diff_ci_lo=dlo, diff_ci_hi=dhi))
    return pd.DataFrame(rows), log


# ----------------------------------------------------------------------------- output
def emit(name: str, t: pd.DataFrame) -> None:
    t.to_csv(OUT / f"{name}.csv", index=False)
    show = t.copy()
    for c in show.columns:
        if show[c].dtype.kind == "f":
            show[c] = show[c].map(lambda x: f"{x:.3f}")
    print(f"\n### {name}\n")
    print(show.to_markdown(index=False))


def main() -> None:
    df = load()
    rep = df[df["is_repeat"]].copy()
    rep["gap_class"] = rep["gap_class"].astype(str)

    # H2a: rates with CIs
    for kind in ["correction", "review"]:
        d = rep[rep["kind"] == kind]
        emit(f"rq2_{kind}_by_split", rate_table(d, ["split"], kind))
        emit(f"rq2_{kind}_by_gap", rate_table(d, ["gap_class"], kind))
        emit(f"rq2_{kind}_by_tercile", rate_table(d, ["tercile"], kind))
        emit(f"rq2_{kind}_by_qtype" + (f"_chance_{ARGS.chance}" if kind == "correction" else ""), rate_table(d, ["qtype"], kind))
        emit(f"rq2_{kind}_by_gap_x_tercile_x_qtype" + (f"_chance_{ARGS.chance}" if kind == "correction" else ""), rate_table(d, ["qtype", "tercile", "gap_class"], kind))

    # H2b: review retention vs log(gap)
    rv = rep[(rep["kind"] == "review") & (rep["gap_s"] > 0)]
    res = logit_slope(rv["response"].to_numpy(float), np.log(rv["gap_s"].to_numpy(float)), rv["uid"].to_numpy())
    emit("rq2_h2b_retention_vs_loggap", pd.DataFrame([res]))
    for q in rv["qtype"].unique():
        s = rv[rv["qtype"] == q]
        r = logit_slope(s["response"].to_numpy(float), np.log(s["gap_s"].to_numpy(float)), s["uid"].to_numpy(), B=300)
        emit(f"rq2_h2b_retention_vs_loggap_{q}", pd.DataFrame([r]))

    # H2c: matched post-event change
    table, log = h2c(df)
    print(f"\n### rq2_h2c_matching_log ({KC_TAG})\n")
    for k, v in log.items():
        print(f"  {k}: {v}")
    log["kc_unit"] = KC_TAG
    pd.DataFrame([log]).to_csv(OUT / f"rq2_h2c_matching_log_{KC_TAG}.csv", index=False)
    emit(f"rq2_h2c_matched_change_{KC_TAG}", table)
    print(f"\nwrote tables to {OUT}/")


if __name__ == "__main__":
    main()
"""RQ1: prevalence of cross-batch re-attempts in XES3G5M.

Run from the repo root after reconstruct.py and difficulty.py:
    uv run python src/audit/prevalence_tables.py 2>&1 | tee docs/exploration/$(date +%F)_rq1_prevalence.log

Reads   data/processed/xes3g5m_clean.parquet
        data/processed/item_difficulty.csv
        data/raw/XES3G5M/metadata/questions.json      (question type; table skipped if absent)
Writes  data/processed/rq1/<table>.csv, one per stratifier, pooled and per split,
        and prints every table as markdown for the log.

Definitions (as in reconstruct.py and difficulty.py):
  repeat      attempt >= 1 on the same (uid, question) in a strictly later batch
  correction  repeat whose previous attempt was wrong;  review: previous attempt was right
  gap class   <1h, <1d, <7d, 7d+ between the two attempts
  tercile     easy / medium / hard from train first-attempt accuracy (NaN = sparse or test-only)
  type        question type from questions.json
  attempt     2nd, 3rd, 4th+ attempt at the question
  position    first vs second half of the student's cleaned history (seq_pos < n/2)

Two denominators, stated in every table:
  share_of_interactions  repeat events / all interactions in the stratum  (strata defined for every row)
  share_of_repeats       repeat events in the stratum / all repeat events  (strata defined only for repeats)
Students with at least one repeat are reported per split and pooled.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

IN = Path("data/processed/xes3g5m_clean.parquet")
DIFF = Path("data/processed/item_difficulty.csv")
QJSON = Path("data/raw/XES3G5M/metadata/questions.json")
OUT = Path("data/processed/rq1")
OUT.mkdir(parents=True, exist_ok=True)

TYPE_MAP = {"填空": "fill-in", "单选": "single-choice", "选择": "choice"}  # XES3G5M question types; unknown values kept as-is


def load() -> pd.DataFrame:
    cols = ["split", "uid", "question", "response", "seq_pos", "attempt", "is_repeat",
            "gap_class", "kind", "prev_response"]
    df = pd.read_parquet(IN, columns=cols)

    # difficulty tercile
    diff = pd.read_csv(DIFF, usecols=["question", "tercile"])
    df = df.merge(diff, on="question", how="left")
    df["tercile"] = df["tercile"].fillna("no tercile")

    # sequence position: first vs second half of the student's history
    n = df.groupby("uid")["seq_pos"].transform("size")
    df["position"] = np.where(df["seq_pos"] < n / 2, "first half", "second half")

    # attempt number, labelled for the repeat tables
    df["attempt_no"] = pd.cut(df["attempt"], bins=[-0.5, 0.5, 1.5, 2.5, np.inf],
                              labels=["1st", "2nd", "3rd", "4th+"])

    # question type
    if QJSON.exists():
        with open(QJSON, encoding="utf-8") as f:
            qmeta = json.load(f)
        qtype = {int(k): TYPE_MAP.get(v.get("type", ""), v.get("type", "unknown")) for k, v in qmeta.items()}
        df["qtype"] = df["question"].map(qtype).fillna("unknown")
    else:
        print(f"note: {QJSON} not found; question-type table skipped")
        df["qtype"] = None
    return df


def by_interactions(df: pd.DataFrame, strat: str) -> pd.DataFrame:
    """Rows: stratum x split (+ pooled). Denominator: all interactions in the stratum."""
    def agg(d: pd.DataFrame) -> pd.Series:
        r = d[d["is_repeat"]]
        return pd.Series({
            "interactions": len(d),
            "students": d["uid"].nunique(),
            "repeat_events": len(r),
            "share_of_interactions": len(r) / len(d) if len(d) else np.nan,
            "corrections": int((r["kind"] == "correction").sum()),
            "reviews": int((r["kind"] == "review").sum()),
            "students_with_repeat": r["uid"].nunique(),
            "share_students_with_repeat": r["uid"].nunique() / d["uid"].nunique() if len(d) else np.nan,
        })
    df = df.assign(_strat=df[strat])          # keep the stratifier available inside agg
    parts = []
    for split, d in df.groupby("split"):
        t = d.groupby("_strat", observed=True).apply(agg, include_groups=False).reset_index()
        t.insert(0, "split", split)
        parts.append(t)
    t = df.groupby("_strat", observed=True).apply(agg, include_groups=False).reset_index()
    t.insert(0, "split", "pooled")
    parts.append(t)
    return pd.concat(parts, ignore_index=True).rename(columns={"_strat": strat})


def by_repeats(df: pd.DataFrame, strat: str) -> pd.DataFrame:
    """Rows: stratum x split (+ pooled). Denominator: all repeat events."""
    rep = df[df["is_repeat"]]
    def agg(d: pd.DataFrame, total: int) -> pd.Series:
        return pd.Series({
            "repeat_events": len(d),
            "share_of_repeats": len(d) / total if total else np.nan,
            "corrections": int((d["kind"] == "correction").sum()),
            "reviews": int((d["kind"] == "review").sum()),
            "students": d["uid"].nunique(),
        })
    rep = rep.assign(_strat=rep[strat])
    parts = []
    for split, d in rep.groupby("split"):
        t = d.groupby("_strat", observed=True).apply(lambda g: agg(g, len(d)), include_groups=False).reset_index()
        t.insert(0, "split", split)
        parts.append(t)
    t = rep.groupby("_strat", observed=True).apply(lambda g: agg(g, len(rep)), include_groups=False).reset_index()
    t.insert(0, "split", "pooled")
    parts.append(t)
    return pd.concat(parts, ignore_index=True).rename(columns={"_strat": strat})


def emit(name: str, t: pd.DataFrame) -> None:
    t.to_csv(OUT / f"{name}.csv", index=False)
    show = t.copy()
    for c in ["interactions", "repeat_events", "students", "corrections", "reviews",
              "students_with_repeat"]:
        if c in show:
            show[c] = show[c].astype(int)
    for c in show.columns:
        if c.startswith("share"):
            show[c] = show[c].map(lambda x: f"{x:.4f}")
    print(f"\n### {name}\n")
    print(show.to_markdown(index=False))


def main() -> None:
    df = load()

    # headline, pooled and per split
    emit("rq1_overall", by_interactions(df.assign(all="all"), "all").drop(columns="all"))

    # denominators: all interactions
    emit("rq1_by_tercile", by_interactions(df, "tercile"))
    emit("rq1_by_position", by_interactions(df, "position"))
    if df["qtype"].notna().any():
        emit("rq1_by_qtype", by_interactions(df, "qtype"))

    # denominators: repeat events
    emit("rq1_by_kind", by_repeats(df, "kind"))
    emit("rq1_by_gap_class", by_repeats(df, "gap_class"))
    emit("rq1_by_attempt", by_repeats(df, "attempt_no"))

    # crosses the analysis plan names: kind x gap, kind x tercile
    rep = df[df["is_repeat"]].copy()
    rep["kind_gap"] = rep["kind"] + " / " + rep["gap_class"].astype(str)
    emit("rq1_by_kind_x_gap", by_repeats(rep, "kind_gap"))
    rep["kind_tercile"] = rep["kind"] + " / " + rep["tercile"].astype(str)
    emit("rq1_by_kind_x_tercile", by_repeats(rep, "kind_tercile"))

    # contingency check: share of repeats without a tercile
    no_terc = (rep["tercile"] == "no tercile").mean()
    print(f"\nrepeat events without a difficulty tercile: {no_terc:.4f} "
          f"({'exceeds' if no_terc > 0.15 else 'within'} the 15% contingency threshold)")
    print(f"\nwrote {len(list(OUT.glob('rq1_*.csv')))} tables to {OUT}/")


if __name__ == "__main__":
    main()
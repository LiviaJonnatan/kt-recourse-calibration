"""First look at XES3G5M question-level files.

Run from the repo root:
    uv run python src/audit/explore_xes3g5m.py

Prints counts for docs/reproduction.md and writes two small tables to
data/processed/explore/. The result here is a sanity check.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("data/raw/XES3G5M")
QL = ROOT / "question_level"
META = ROOT / "metadata"
OUT = Path("data/processed/explore")
OUT.mkdir(parents=True, exist_ok=True)

SEQ_COLS = ["questions", "concepts", "responses", "timestamps", "selectmasks"]


def load(name: str) -> pd.DataFrame:
    df = pd.read_csv(QL / name, dtype=str)
    print(f"\n=== {name} ===")
    print("columns:", list(df.columns))
    assert "is_repeat" not in df.columns, "question-level file should not have is_repeat"
    print("rows (subsequences):", len(df))
    print("unique uid:", df["uid"].nunique())
    if "fold" in df.columns:
        print("fold counts:\n", df["fold"].value_counts().sort_index().to_string())
    return df


def explode(df: pd.DataFrame) -> pd.DataFrame:
    """One row per interaction, keeping subsequence index and position."""
    cols = [c for c in SEQ_COLS if c in df.columns]
    missing = [c for c in SEQ_COLS if c not in df.columns]
    if missing:
        print("note: columns absent in this file:", missing)
    parts = {c: df[c].str.split(",") for c in cols}
    lens = parts["questions"].str.len()
    for c in cols:
        assert (lens == parts[c].str.len()).all(), f"{c} length mismatch with questions"
    print("subsequence length: min", lens.min(), "max", lens.max(), "mean", round(lens.mean(), 1))
    print("subsequences at exactly 200 (truncation signature):", int((lens == 200).sum()), "of", len(df))

    long = pd.DataFrame({
        "uid": df["uid"].repeat(lens).values,
        "subseq": np.repeat(np.arange(len(df)), lens),
        "pos": np.concatenate([np.arange(n) for n in lens]),
        "question": np.concatenate(parts["questions"].values),
        "concepts": np.concatenate(parts["concepts"].values),
        "response": np.concatenate(parts["responses"].values).astype(int),
        "ts": np.concatenate(parts["timestamps"].values).astype(np.int64),
    })
    if "selectmasks" in parts:
        long["mask"] = np.concatenate(parts["selectmasks"].values).astype(int)
        print("selectmask==1:", int((long["mask"] == 1).sum()), " (==-1 / padded:", int((long["mask"] != 1).sum()), ")")
    else:
        long["mask"] = 1
    print("interactions:", len(long))
    return long


def per_uid_fragmentation(long: pd.DataFrame, label: str) -> pd.Series:
    n_sub = long.groupby("uid")["subseq"].nunique()
    print(f"\n[{label}] subsequences per uid:")
    print(n_sub.describe().round(2).to_string())
    print("uids with 1 subsequence:", int((n_sub == 1).sum()), f"({(n_sub == 1).mean():.1%})")
    print("uids with 5+ subsequences:", int((n_sub >= 5).sum()), f"({(n_sub >= 5).mean():.1%})")
    return n_sub


def timestamp_checks(long: pd.DataFrame, label: str) -> None:
    g = long.sort_values(["uid", "ts", "subseq", "pos"]).groupby("uid")
    mono = g["ts"].apply(lambda s: bool((s.diff().dropna() >= 0).all()))
    print(f"\n[{label}] timestamps monotonic within uid (after sort by ts): {mono.mean():.1%}")
    diffs = g["ts"].diff().dropna() / 1000
    print("gap to previous interaction (seconds): share exactly 0:", f"{(diffs == 0).mean():.1%}",
          "| share < 60 s:", f"{(diffs < 60).mean():.1%}",
          "| median non-zero gap (s):", int(diffs[diffs > 0].median()))
    ts_min = pd.to_datetime(long["ts"].min(), unit="ms")
    ts_max = pd.to_datetime(long["ts"].max(), unit="ms")
    print("date range:", ts_min.date(), "to", ts_max.date())


def repeat_preview(long: pd.DataFrame, label: str) -> pd.DataFrame:
    """Within-uid repeats of the same question. Gap classes by timestamp."""
    s = long.sort_values(["uid", "ts", "subseq", "pos"]).copy()
    s["attempt"] = s.groupby(["uid", "question"]).cumcount()
    s["prev_resp"] = s.groupby(["uid", "question"])["response"].shift()
    s["prev_ts"] = s.groupby(["uid", "question"])["ts"].shift()
    s["prev_subseq"] = s.groupby(["uid", "question"])["subseq"].shift()
    rep = s[s["attempt"] >= 1].copy()
    rep["gap_s"] = (rep["ts"] - rep["prev_ts"]) / 1000
    rep["gap_class"] = pd.cut(rep["gap_s"], bins=[-1, 0, 3600, 86400, 7 * 86400, np.inf],
                              labels=["same_batch", "<1h", "<1d", "<7d", "7d+"])
    rep["kind"] = np.where(rep["prev_resp"] == 0, "correction", "review")
    rep["crosses_subseq"] = rep["subseq"] != rep["prev_subseq"]

    n_uid = long["uid"].nunique()
    print(f"\n[{label}] REPEAT PREVIEW")
    print("repeat events:", len(rep), f"({len(rep) / len(long):.2%} of interactions)")
    print("uids with >=1 repeat:", rep["uid"].nunique(), f"({rep['uid'].nunique() / n_uid:.1%} of uids)")
    print("by kind:\n", rep["kind"].value_counts().to_string())
    print("by gap class:\n", rep["gap_class"].value_counts().sort_index().to_string())
    print("kind x gap:\n", pd.crosstab(rep["kind"], rep["gap_class"]).to_string())
    print("repeats crossing a subsequence boundary:", int(rep["crosses_subseq"].sum()),
          f"({rep['crosses_subseq'].mean():.1%})")
    print("outcome on repeat | kind:\n", rep.groupby("kind")["response"].mean().round(3).to_string())
    return rep


def metadata_checks() -> None:
    with open(META / "questions.json") as f:
        qs = json.load(f)
    print("\n=== metadata/questions.json ===")
    print("questions:", len(qs))
    k0 = next(iter(qs))
    print("example key:", k0, "| fields:", list(qs[k0].keys()))
    types = Counter(v.get("type") for v in qs.values())
    print("type counts (0=fill-in, 1=multiple-choice):", dict(types))
    n_kc = Counter(len(v.get("kc_routes", [])) for v in qs.values())
    print("number of kc_routes per question:", dict(sorted(n_kc.items())))


def main() -> None:
    train = load("train_valid_sequences_quelevel.csv")
    test = load("test_quelevel.csv")

    overlap = set(train["uid"]) & set(test["uid"])
    print("\nuids in BOTH train and test:", len(overlap))

    long_tr = explode(train)
    long_te = explode(test)

    per_uid_fragmentation(long_tr, "train").to_csv(OUT / "train_subseq_per_uid.csv")
    per_uid_fragmentation(long_te, "test").to_csv(OUT / "test_subseq_per_uid.csv")

    timestamp_checks(long_tr, "train")
    timestamp_checks(long_te, "test")

    q_tr = set(long_tr["question"])
    q_te = set(long_te["question"])
    print("\nunique questions: train", len(q_tr), "| test", len(q_te), "| union", len(q_tr | q_te))
    print("questions in test but not train:", len(q_te - q_tr))

    rep_tr = repeat_preview(long_tr, "train")
    rep_te = repeat_preview(long_te, "test")
    pd.concat([rep_tr.assign(split="train"), rep_te.assign(split="test")]).to_csv(
        OUT / "repeat_events_preview.csv", index=False)

    metadata_checks()
    print("\nwrote:", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
"""Item difficulty from first attempts on train folds only.

Run from the repo root after reconstruct.py:
    uv run python src/audit/difficulty.py

Difficulty = 1 - accuracy on first attempts, train split only, questions
with at least MIN_ATTEMPTS first attempts. Terciles are assigned among
qualifying questions (easy / medium / hard). Test-only questions and
sparse questions get NaN and are excluded from difficulty-stratified
analyses (counts reported).
Writes data/processed/item_difficulty.csv
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

IN = Path("data/processed/xes3g5m_clean.parquet")
OUT = Path("data/processed/item_difficulty.csv")
MIN_ATTEMPTS = 30

df = pd.read_parquet(IN, columns=["split", "question", "attempt", "response", "first_kc", "n_kc"])
first = df[(df["split"] == "train") & (df["attempt"] == 0)]

item = (first.groupby("question")
        .agg(n_first_attempts=("response", "size"), acc=("response", "mean"),
             first_kc=("first_kc", "first"), n_kc=("n_kc", "first"))
        .reset_index())
item["difficulty"] = 1 - item["acc"]
ok = item["n_first_attempts"] >= MIN_ATTEMPTS
item.loc[ok, "tercile"] = pd.qcut(item.loc[ok, "difficulty"], 3, labels=["easy", "medium", "hard"])

all_q = pd.Series(sorted(df["question"].unique()), name="question")
item = all_q.to_frame().merge(item, on="question", how="left")

print("questions total:", len(item))
print("with >= %d train first attempts:" % MIN_ATTEMPTS, int(ok.sum()))
print("test-only or sparse (no tercile):", int(item["tercile"].isna().sum()))
print("difficulty quantiles among qualifying:\n",
      item.loc[item["tercile"].notna(), "difficulty"].quantile([0, .25, .5, .75, 1]).round(3).to_string())
print("tercile boundaries:\n",
      item.groupby("tercile", observed=True)["difficulty"].agg(["min", "max", "count"]).round(3).to_string())

item.to_csv(OUT, index=False)
print("wrote", OUT)
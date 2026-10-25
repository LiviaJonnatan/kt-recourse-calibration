"""Decide what same-batch repeats are: retries, duplicate logs, or repeated
worksheet items.

Run from the repo root after check_mask.py:
    uv run python src/audit/inspect_same_batch.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

IN = Path("data/processed/explore")

real = pd.read_parquet(IN / "train_clean_long.parquet")
real = real.sort_values(["uid", "ts", "row", "pos"]).copy()
real["seq_pos"] = real.groupby("uid").cumcount()
real["attempt"] = real.groupby(["uid", "question"]).cumcount()
grp = real.groupby(["uid", "question"])
real["prev_resp"] = grp["response"].shift()
real["prev_ts"] = grp["ts"].shift()
real["prev_seq_pos"] = grp["seq_pos"].shift()

rep = real[real["attempt"] >= 1].copy()
rep["same_batch"] = rep["ts"] == rep["prev_ts"]
rep["pos_gap"] = (rep["seq_pos"] - rep["prev_seq_pos"]).astype(int)
rep["same_answer"] = rep["response"] == rep["prev_resp"]
rep["kind"] = np.where(rep["prev_resp"] == 0, "correction", "review")

sb = rep[rep["same_batch"]]
print("same-batch repeat events:", len(sb))
print("\nsame answer as previous attempt:", f"{sb['same_answer'].mean():.1%}")
print("transition (prev -> now):\n", pd.crosstab(sb["prev_resp"], sb["response"]).to_string())
print("\nposition gap (how many interactions between the two attempts):")
print(sb["pos_gap"].value_counts().sort_index().head(10).to_string())
print("adjacent (gap == 1):", f"{(sb['pos_gap'] == 1).mean():.1%}")

# Compare: non-same-batch repeats, for contrast
nsb = rep[~rep["same_batch"]]
print("\nFOR CONTRAST, repeats in a later batch:")
print("same answer as previous attempt:", f"{nsb['same_answer'].mean():.1%}")
print("transition:\n", pd.crosstab(nsb["prev_resp"], nsb["response"]).to_string())
print(pd.crosstab([sb["kind"], sb["same_answer"]], sb["pos_gap"] == 1,
                  rownames=["kind", "same_answer"], colnames=["adjacent"]).to_string())

# Is the same-batch pattern concentrated in a few questions?
top = sb["question"].value_counts().head(10)
print("\ntop questions by same-batch repeat count:\n", top.to_string())
print("share of same-batch repeats in top 50 questions:",
      f"{sb['question'].value_counts().head(50).sum() / len(sb):.1%}")

# Adjacent, same-answer pairs: the duplicate-log signature
dup_sig = sb[(sb["pos_gap"] == 1) & sb["same_answer"]]
print("\nadjacent + same answer (duplicate-log signature):", len(dup_sig), f"({len(dup_sig) / len(sb):.1%} of same-batch)")

# Print 30 examples with context so a human can judge
print("\n=== 30 examples (uid, question, prev_resp -> resp, pos gap, surrounding sequence) ===")
rng = np.random.default_rng(2026)
for _, r in sb.sample(30, random_state=2026).iterrows():
    uid, q = r["uid"], r["question"]
    lo, hi = int(r["prev_seq_pos"]) - 2, int(r["seq_pos"]) + 2
    ctx = real[(real["uid"] == uid) & (real["seq_pos"].between(lo, hi))]
    seq = " ".join(f"{'[' if x == q else ''}{x}:{y}{']' if x == q else ''}"
                   for x, y in zip(ctx["question"], ctx["response"]))
    print(f"uid {uid} q {q} {int(r['prev_resp'])}->{int(r['response'])} gap {r['pos_gap']:>2} | {seq}")
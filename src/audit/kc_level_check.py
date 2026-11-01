"""How many repeat events have a 10-interaction window on each side, by KC hierarchy level.

Run from the repo root:
    uv run python src/audit/kc_level_check.py 2>&1 | tee docs/exploration/$(date +%F)_kc_level_check.log

kc_routes in questions.json look like  课内知识点----测量----周长----求不规则图形周长----已知边长求周长
(five levels, leaf last). Level k uses the first k components of the question's first route.
For each level this prints the number of distinct nodes, the distribution of same-node interactions
per student-node, and the share of repeat events whose first attempt has >= WINDOW same-node
interactions before it and whose repeat has >= WINDOW same-node interactions after it (the H2c
eligibility rule, without the same-question exclusion).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

IN = Path("data/processed/xes3g5m_clean.parquet")
QJSON = Path("data/raw/XES3G5M/metadata/questions.json")
WINDOW = 10
SEP = "----"

with open(QJSON, encoding="utf-8") as f:
    qmeta = json.load(f)
routes = {int(k): (v.get("kc_routes") or [""])[0].split(SEP) for k, v in qmeta.items()}
max_depth = max(len(r) for r in routes.values())
print(f"questions: {len(routes)}; route depth: max {max_depth}, "
      f"distribution {pd.Series([len(r) for r in routes.values()]).value_counts().sort_index().to_dict()}")

df = pd.read_parquet(IN, columns=["uid", "question", "seq_pos", "attempt", "is_repeat", "prev_seq_pos", "first_kc"])
df = df.sort_values(["uid", "seq_pos"]).reset_index(drop=True)

rows = []
for level in list(range(1, max_depth + 1)) + ["leaf_kc_id"]:
    if level == "leaf_kc_id":
        df["node"] = df["first_kc"].astype(str)
    else:
        df["node"] = df["question"].map(lambda q: SEP.join(routes[q][:level]))
    g = df.groupby(["uid", "node"], sort=False)
    df["rank"] = g.cumcount()
    df["n"] = g["seq_pos"].transform("size")
    per_pair = g.size()
    rep = df[df["is_repeat"]]
    # rank of the first attempt within (uid, node): look it up by (uid, question, attempt 0)
    first_rank = df[df["attempt"] == 0].set_index(["uid", "question"])["rank"]
    fr = first_rank.reindex(pd.MultiIndex.from_arrays([rep["uid"], rep["question"]])).to_numpy()
    before_ok = fr >= WINDOW
    after_ok = (rep["rank"].to_numpy() + WINDOW) < rep["n"].to_numpy()
    share = float((before_ok & after_ok).mean())
    rows.append(dict(level=level, distinct_nodes=df["node"].nunique(),
                     median_per_student_node=float(per_pair.median()), p90=float(per_pair.quantile(.9)),
                     share_pairs_ge_21=float((per_pair >= 2 * WINDOW + 1).mean()),
                     repeat_events_eligible=int((before_ok & after_ok).sum()), share_eligible=share))
    print(f"level {level!s:>11}: nodes {rows[-1]['distinct_nodes']:>6}  median/pair {rows[-1]['median_per_student_node']:>5.1f}  "
          f"p90 {rows[-1]['p90']:>5.1f}  eligible {rows[-1]['repeat_events_eligible']:>7,} ({share:.3f})")

out = pd.DataFrame(rows)
Path("data/processed/rq2").mkdir(parents=True, exist_ok=True)
out.to_csv("data/processed/rq2/kc_level_check.csv", index=False)
print("\n" + out.to_markdown(index=False))
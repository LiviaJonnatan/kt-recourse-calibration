"""(part 1) Emit pyKT-format sequence files from events.parquet so pyKT can train dkt / dkt_forget.

pyKT's KTDataset expects rows already cut to `maxlen` (200) steps and padded with -1:
    fold,uid,questions,concepts,responses,timestamps,selectmasks
Each learner's sequence is split into consecutive 200-step chunks; the last chunk is padded.
concept id = area code, question id = question code (maps saved alongside).
train_valid_sequences.csv: train-split learners, 5 folds by uid hash.
test_sequences.csv (+ an identical test_window_sequences.csv so pyKT's eval does not fail).

Usage: python s13_pykt_export.py --out ../../out/slam --dest ../../data/pykt/slam
Prints num_q / num_c for the data_config.json entry.
"""
import argparse
from pathlib import Path
import numpy as np, pandas as pd

MAXLEN = 200
ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, required=True); ap.add_argument("--dest", type=Path, required=True)
a = ap.parse_args(); a.dest.mkdir(parents=True, exist_ok=True)
d = pd.read_parquet(a.out / "events.parquet", columns=["split", "uid", "seq_pos", "question", "area", "response", "ts"]).sort_values(["uid", "seq_pos"])
d["c"] = d["area"].astype(str).astype("category").cat.codes.astype(int); d["q"] = d["question"].astype("category").cat.codes.astype(int)
pd.DataFrame({"area": d["area"].astype(str), "c": d["c"]}).drop_duplicates().to_csv(a.dest / "concept_map.csv", index=False)
pd.DataFrame({"question": d["question"], "q": d["q"]}).drop_duplicates().to_csv(a.dest / "question_map.csv", index=False)

def pad(v):
    v = list(map(str, v)); return ",".join(v + ["-1"] * (MAXLEN - len(v)))

def rows(part, fold_of):
    out = []
    for uid, g in part.groupby("uid", sort=False):
        q, c, r, t = (g[k].to_numpy() for k in ["q", "c", "response", "ts"])
        for s in range(0, len(g), MAXLEN):
            if len(g) - s < 3: break
            sl = slice(s, s + MAXLEN); n = len(q[sl])
            out.append({"fold": fold_of(uid), "uid": uid, "questions": pad(q[sl]), "concepts": pad(c[sl]), "responses": pad(r[sl]),
                        "timestamps": pad(t[sl] // 1000), "selectmasks": pad([1] * n)})
    return pd.DataFrame(out)

tr = rows(d[d.split == "train"], lambda u: int(pd.util.hash_array(np.array([u], np.int64))[0] % 5))
te = rows(d[d.split == "test"], lambda u: -1)
tr.to_csv(a.dest / "train_valid_sequences.csv", index=False)
te.to_csv(a.dest / "test_sequences.csv", index=False); te.to_csv(a.dest / "test_window_sequences.csv", index=False)
print({"num_q": int(d["q"].max() + 1), "num_c": int(d["c"].max() + 1), "train_rows": len(tr), "test_rows": len(te), "maxlen": MAXLEN})
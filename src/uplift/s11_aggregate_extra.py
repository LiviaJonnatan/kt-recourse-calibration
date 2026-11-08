"""Aggregate s9/s10 outputs over seeds -> out/transfer_table.csv, out/paired_table.csv"""
import argparse, glob, re
from pathlib import Path
import pandas as pd
ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, required=True); a = ap.parse_args()
rows = []
for f in glob.glob(str(a.out / "*" / "s10_paired*_s[0-9]*.csv")):
    p = Path(f); m = re.match(r"s10_paired(.*)_s(\d)\.csv", p.name)
    d = pd.read_csv(f); d["dataset"] = p.parent.name; d["outcome"] = m.group(1) or "_area"; d["seed"] = int(m.group(2)); rows.append(d)
if rows:
    r = pd.concat(rows)
    agg = r.groupby(["dataset", "outcome", "arm"]).agg(gap_vs_pcorrect=("gap_vs_pcorrect", "mean"), ci_lo=("ci_lo", "mean"), ci_hi=("ci_hi", "mean"),
                                                      gap_vs_random=("gap_vs_random", "mean"), ci_lo_r=("ci_lo_r", "mean"), ci_hi_r=("ci_hi_r", "mean"),
                                                      seeds=("seed", "count")).round(3).reset_index()
    agg.to_csv(a.out / "paired_table.csv", index=False); print(agg.to_string(index=False)); print()
rows = []
for f in glob.glob(str(a.out / "s9_transfer*_s[0-9]*.csv")):
    p = Path(f); m = re.match(r"s9_transfer(.*)_s(\d)\.csv", p.name)
    d = pd.read_csv(f); d["outcome"] = m.group(1) or "_area"; d["seed"] = int(m.group(2)); rows.append(d)
if rows:
    r = pd.concat(rows)
    agg = r.groupby(["outcome", "arm", "model_from", "evaluated_on"]).agg(tau_lcb=("tau_lcb", "mean"), tau_lcb_sd=("tau_lcb", "std"), tau_t=("tau_t", "mean"),
                                                                           p_dkt=("p_dkt", "mean"), random=("random", "mean"), seeds=("seed", "count")).round(3).reset_index()
    agg.to_csv(a.out / "transfer_table.csv", index=False); print(agg.to_string(index=False))
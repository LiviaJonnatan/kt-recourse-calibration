import argparse, glob, re
from pathlib import Path
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args()

rows = []
for f in glob.glob(str(a.out / "*" / "s5_event_qini*_s[0-9]*.csv")):
    p = Path(f)
    m = re.match(r"s5_event_qini(.*)_s(\d)(_hr[\d.]+)?\.csv", p.name)
    if not m:
        continue
    d = pd.read_csv(f)
    d["dataset"] = p.parent.name
    d["outcome"] = m.group(1) or "_area"
    d["seed"] = int(m.group(2))
    d["headroom"] = m.group(3) or ""
    rows.append(d)

r = pd.concat(rows)
keep = r[r["ranker"].isin(["random", "p_dkt", "mu1", "tau_t", "tau_dr", "tau_lcb"])]
agg = (keep.groupby(["dataset", "outcome", "headroom", "arm", "ranker"])["uplift_top20"]
       .agg(mean="mean", sd="std", n="count").round(3).reset_index())
agg.to_csv(a.out / "headline_table.csv", index=False)
pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 500)
print(agg.to_string(index=False))
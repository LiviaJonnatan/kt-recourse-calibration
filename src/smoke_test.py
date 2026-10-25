"""End-to-end sanity check for a fresh clone.

    uv run python src/smoke_test.py

Checks, in order, and stops at the first failure:
  1. torch imports and a device is chosen
  2. .env is loaded (PYTORCH_ENABLE_MPS_FALLBACK, KTCF_ROOT, DATA_ROOT)
  3. the clean parquet exists and has the expected columns and row count
  4. item_difficulty.csv exists
  5. a 2-layer LSTM (DKT-shaped) runs a forward pass on the device
  6. (optional) pyKT imports, if installed
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # so `common` imports from src/

from dotenv import load_dotenv

load_dotenv()

import torch

from common.device import get_device

EXPECTED_COLS = {"split", "uid", "question", "response", "ts", "seq_pos", "attempt", "is_repeat", "kind", "gap_class"}
EXPECTED_ROWS = 5_491_578


def ok(msg: str) -> None:
    print(f"  ok   {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL {msg}")
    sys.exit(1)


print("1. torch / device")
device = get_device()
ok(f"torch {torch.__version__}")

print("2. environment")
for var in ("PYTORCH_ENABLE_MPS_FALLBACK", "KTCF_ROOT", "DATA_ROOT"):
    val = os.environ.get(var)
    (ok if val else fail)(f"{var} = {val!r}" if val else f"{var} not set (add it to .env)")
data_root = Path(os.environ["DATA_ROOT"])
ktcf_root = Path(os.environ["KTCF_ROOT"])
(ok if ktcf_root.exists() else fail)(f"KTCF_ROOT exists: {ktcf_root.resolve()}" if ktcf_root.exists()
                                     else f"KTCF_ROOT not found at {ktcf_root.resolve()}; clone woojinkim1021/ktcf there")

print("3. clean table")
pq = data_root / "processed" / "xes3g5m_clean.parquet"
if not pq.exists():
    fail(f"{pq} missing; run src/audit/reconstruct.py")
import pandas as pd  # noqa: E402

df = pd.read_parquet(pq, columns=["split", "uid"])
missing = EXPECTED_COLS - set(pd.read_parquet(pq).columns) if len(df) < 10 else EXPECTED_COLS - set(
    pd.read_parquet(pq, columns=list(EXPECTED_COLS)).columns)
(ok if not missing else fail)("all expected columns present" if not missing else f"missing columns: {sorted(missing)}")
(ok if len(df) == EXPECTED_ROWS else fail)(f"{len(df):,} rows" if len(df) == EXPECTED_ROWS
                                           else f"{len(df):,} rows, expected {EXPECTED_ROWS:,}; reconstruct.py output changed")
ok(f"{df['uid'].nunique():,} students across {df['split'].nunique()} splits")

print("4. difficulty table")
dcsv = data_root / "processed" / "item_difficulty.csv"
(ok if dcsv.exists() else fail)(f"{dcsv}" if dcsv.exists() else f"{dcsv} missing; run src/audit/difficulty.py")

print("5. tiny DKT forward pass")
n_items, hidden, batch, seq = 100, 32, 4, 20
emb = torch.nn.Embedding(2 * n_items, hidden).to(device)
lstm = torch.nn.LSTM(hidden, hidden, batch_first=True).to(device)
head = torch.nn.Linear(hidden, n_items).to(device)
x = torch.randint(0, 2 * n_items, (batch, seq), device=device)
with torch.no_grad():
    out, _ = lstm(emb(x))
    logits = head(out)
(ok if logits.shape == (batch, seq, n_items) else fail)(f"logits shape {tuple(logits.shape)} on {device}")

print("6. pyKT (optional)")
try:
    import pykt  # noqa: F401

    ok(f"pykt importable from {Path(pykt.__file__).parent}")
except ImportError:
    print("  skip pykt not installed yet (add with: uv add --editable ../ktcf/pykt)")

print("6. pyKT (KTCF's vendored copy)")
try:
    import common.ktcf_path  # noqa: F401
    import pykt
    ok(f"pykt importable from {Path(pykt.__file__).parent}")
except Exception as e:  # noqa: BLE001
    fail(f"pykt import failed: {e}")

print("\nall checks passed")
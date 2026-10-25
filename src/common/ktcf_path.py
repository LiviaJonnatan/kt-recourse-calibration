"""Make KTCF's vendored pyKT importable. Import this before `import pykt`."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
_root = Path(os.environ.get("KTCF_ROOT", "../ktcf")).resolve()
if not (_root / "pykt").is_dir():
    raise ImportError(f"KTCF_ROOT={_root} has no pykt/ folder; clone woojinkim1021/ktcf there")
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
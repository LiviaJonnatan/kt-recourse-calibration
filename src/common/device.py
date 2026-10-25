"""Choose the torch device once, in one place.

    from common.device import get_device
    device = get_device()
    model.to(device)

Order: MPS (Apple Silicon) → CUDA → CPU. Override with DEVICE=cpu|mps|cuda
in the environment or .env.
"""
from __future__ import annotations

import os

import torch


def get_device(verbose: bool = True) -> torch.device:
    forced = os.environ.get("DEVICE")
    if forced:
        dev = torch.device(forced)
    elif torch.backends.mps.is_available():
        dev = torch.device("mps")
    elif torch.cuda.is_available():
        dev = torch.device("cuda")
    else:
        dev = torch.device("cpu")
    if verbose:
        extra = ""
        if dev.type == "mps" and os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK") != "1":
            extra = "  (warning: PYTORCH_ENABLE_MPS_FALLBACK is not set; unsupported ops will crash instead of falling back to CPU)"
        if dev.type == "cuda":
            extra = f"  ({torch.cuda.get_device_name(0)})"
        print(f"device: {dev}{extra}")
    return dev
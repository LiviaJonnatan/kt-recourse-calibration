# Setup

How to get a working environment for this repo, and a running log of every problem hit and how it was fixed. If you change anything about the environment, add a dated entry to the log at the bottom.

## Target environment

- macOS on Apple Silicon (primary development). Linux with an NVIDIA GPU works too; see "Other platforms".
- Python 3.12, managed by `uv`.
- PyTorch with the MPS backend (ships in the default PyPI wheel on macOS).
- pyKT as an editable dependency, so local fixes take effect without reinstalling.
- The KTCF reference repo cloned as a sibling folder, `../ktcf`, not inside this repo.

## First-time setup

1. Install uv.

   ```
   brew install uv        # or: curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone this repo and the KTCF repo side by side, outside any synced folder.

   ```
   mkdir -p ~/code && cd ~/code
   git clone https://github.com/LiviaJonnatan/kt-recourse-calibration
   git clone https://github.com/woojinkim1021/ktcf
   cd kt-recourse-calibration
   ```

3. Create the environment from the lockfile.

   ```
   uv sync
   ```

   This installs exactly the versions in `uv.lock`. Do not use `pip install` in this environment; it bypasses the lockfile.

4. Verify PyTorch sees the GPU.

   ```
   uv run python -c "import torch; print(torch.__version__, torch.backends.mps.is_available())"
   ```

   Expect `True` on Apple Silicon. On Linux check `torch.cuda.is_available()` instead.

5. Download the datasets into `data/raw/` following `data/README.md`.

6. Run the smoke test.

   ```
   uv run python src/smoke_test.py
   ```

   It loads one XES3G5M file, imports pyKT, and runs a forward pass of a tiny DKT on the available device. If it passes, you are set up.

## Environment variables

Put these in a `.env` at the repo root (gitignored) or export them in your shell.

| Variable | Value | Why |
| --- | --- | --- |
| `PYTORCH_ENABLE_MPS_FALLBACK` | `1` | pyKT uses a few ops MPS does not implement; with this set they run on CPU instead of crashing. Slower for those ops, but correct. |
| `KTCF_ROOT` | `../ktcf` | Where scripts look for the KTCF reference code and its metadata (English KC names, saved models). |
| `DATA_ROOT` | `data` | Lets a teammate point at a different disk if needed. |

Scripts load `.env` via `python-dotenv`.

## How the dependencies were chosen

- `pyproject.toml` is the source of truth; `uv.lock` pins the exact resolution. Both are committed.
- KTCF's `requirements.txt` was **not** installed as-is. Each package was added with `uv add <name>` and left unpinned unless the resolver could not find a version compatible with current torch. Any explicit pin has a comment in `pyproject.toml` saying why, and an entry in the log below.
- pyKT is added as an editable path dependency pointing at the copy vendored in the KTCF repo (or a separate clone if that copy turns out to be stale; the log records which):

  ```
  uv add --editable ../ktcf/pykt
  ```

- Direct dependencies: `torch`, `pandas`, `polars`, `numpy`, `scipy`, `scikit-learn`, `matplotlib`, `tqdm`, `jupyter`, `python-dotenv`, `pyyaml`.

## Running things

- Always prefix with `uv run`, e.g. `uv run python src/audit/reconstruct.py --dataset xes3g5m`.
- Notebooks: `uv run jupyter lab`. Keep notebooks for exploration only; anything that produces a number in a draft lives in a script under `src/`.
- Seeds: every script takes `--seed`, default 2026.

## Making the KTCF code device-agnostic

The reference code assumes CUDA. Rather than editing the KTCF repo in place, patches are kept in `src/ktcf_patches/` and applied by `src/ktcf_patches/apply.py`. Known patterns to patch:

- `.cuda()` → `.to(device)` where `device` is chosen by `src/common/device.py` (MPS if available, else CUDA, else CPU).
- `torch.cuda.is_available()` guards → `device.type != "cpu"`.
- Hard-coded `results/` or dataset paths → read from `KTCF_ROOT` / `DATA_ROOT`.

Log each patch below so it can be reapplied when the upstream repo changes.

## Other platforms

- **Linux + NVIDIA:** `uv sync` installs the CPU/MPS wheel by default. Add the CUDA index as a platform-specific source in `pyproject.toml` (see uv docs on PyTorch indexes) rather than editing the lockfile by hand. Record the CUDA version in the log.
- **Google Colab (fallback for model sweeps):** clone the repo, `pip install uv && uv sync`, mount Drive for `data/raw/`. Expect session timeouts; checkpoint every epoch.

## Log

Add entries at the top. Format: date, who, what broke or changed, what was done, why.

### YYYY-MM-DD — <name>

- **Problem:**
- **Fix:**
- **Why this and not something else:**

### 2026-10-25 — LJ

- **Problem:** KTCF vendors pyKT as a bare source folder; `uv add --editable` rejects it.
- **Fix:** import via `sys.path` from `KTCF_ROOT` (`src/common/ktcf_path.py`); pyKT’s dependencies added manually from `../ktcf/requirements.txt` (list them). Upstream pykt-toolkit deferred to later.
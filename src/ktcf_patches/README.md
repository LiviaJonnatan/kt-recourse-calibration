# KTCF patches

The KTCF reference implementation (https://github.com/woojinkim1021/ktcf) is not part of this repository. We keep two sibling clones:

- `../ktcf` — unmodified reference, pinned to commit `a96906afa7525b60e1847284d0a2db13685cc670`. Never edited. Used only to diff against.
- `../ktcf-work` — the copy every run and import uses (`KTCF_ROOT=../ktcf-work` in `.env`). All changes to it are recorded here and captured in `ktcf-work.patch`.

Rule: never edit `../ktcf`. Edit `../ktcf-work`, add a row to the table below, regenerate the patch, commit both.

## Rebuild `../ktcf-work` from scratch

From this repository's root:

```
git clone https://github.com/woojinkim1021/ktcf ../ktcf
git -C ../ktcf checkout a96906afa7525b60e1847284d0a2db13685cc670
cp -r ../ktcf ../ktcf-work
patch -d ../ktcf-work -p1 < src/ktcf_patches/ktcf-work.patch
```

Then stage the data (see `data/README.md`): copy the release's `kc_level/*` and `metadata/*` into `../ktcf-work/data/XES3G5M/`, make it writable, and run `src/1_data_preprocessing/preprocess_XES3G5M.py` and `create_kc_network.py` from inside `../ktcf-work`.

## Regenerate the patch after any edit

```
diff -ruN --exclude=data --exclude=results --exclude=__pycache__ --exclude='*.pkl' --exclude='*.ckpt' ../ktcf ../ktcf-work > src/ktcf_patches/ktcf-work.patch
```

Open the result and confirm it contains only the rows in the table below.

## Patch table

| ID | File | Change | Reason |
| --- | --- | --- | --- |
| P0 | `pykt/models/init_model.py:162` | `torch.load(..., map_location="cpu")` | checkpoint saved from CUDA tensors; no effect on numbers. Same call exists at `src/2_dkt_training_eval/wandb_train.py:163` (patch if retraining) |
| P1 | `src/run.py` | delete `if idx==1: break` | evaluate the sampled 200, not 1 |

## Known code facts (not patched; documented in `docs/reproduction.md`)

- `loss_prox` (scipy `hamming`) and `loss_kc` are Python floats and carry no gradient; only `loss_pred` drives the optimizer.
- Validity thresholds raw `cf_r`; sparsity and KC distance threshold `sigmoid(cf_r)`.
- `kc_mask` is parsed by `run.py` but unused.
- The paper's η = 1e−4 does not match the code's `--lr 0.01` default.
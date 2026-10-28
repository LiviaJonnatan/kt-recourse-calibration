# KTCF reproduction

Reference: Kim, Lee, Kim. *KTCF: Actionable Recourse in Knowledge Tracing via Counterfactual Explanations for Education.* AAAI 2026 (AI for Social Impact track, oral). arXiv 2601.09156. Code: https://github.com/woojinkim1021/ktcf, commit `a96906afa7525b60e1847284d0a2db13685cc670` (4 commits, no releases, no licence file).

Our commit at the time of this reproduction: `786f553c550a9fdd74839f121ad6f2d1d9205a9d`.

## 1. Environment

| Package | KTCF `requirements.txt` | Ours | Note |
| --- | --- | --- | --- |
| Python | 3.12.11 | 3.12 | |
| torch | 2.7.1+cu128 | 2.14.1` | CUDA wheel dropped; CPU/MPS build |
| numpy | 2.0.0 | 2.5.4 | unpinned |
| pandas | 2.2.3 | 3.1.0 | unpinned |
| scipy | 1.13.1 | 1.18.1 | `hamming` used in `cf_generator.py` |
| networkx | 3.5 | 3.7 | KC graph |
| matplotlib | 3.10.0 | 3.11.2 | figures only |
| wandb | 0.21.0 | 0.31.0 | always run with `--use_wandb 0` |
| scikit-learn | (not listed) | 1.9.1 | needed by pyKT `evaluate_model.py` |

KTCF hardware: Ubuntu 20.04, RTX 4090, CUDA 12.8. Ours: Apple Silicon; the reproduction runs on **CPU** because every KTCF entry point sets `device = "cpu" if not torch.cuda.is_available() else "cuda"` and calls `torch.use_deterministic_algorithms(True)`. MPS is used only for Phase 4 training.

Working copy: `../ktcf-work` (patched, all runs); `../ktcf` is the unmodified reference. `KTCF_ROOT=../ktcf-work`.

pyKT: KTCF vendors a trimmed pyKT v1.0.0 (`pykt/`) with one modification, `pykt/models/dkt.py`, which adds a differentiable `soft_embedding` so the counterfactual optimizer can backpropagate into a continuous response vector. Parameter names match upstream DKT, so the checkpoint loads.

## 2. Preprocessing (what the code actually does)
| Question | Answer | Where |
| --- | --- | --- |
| Input files | **KC-level**: `train_valid_sequences.csv` for training (unchanged); `test.csv` (full sequences) and `test_question_window_sequences.csv` for test | `configs/data_config.json` (`input_type: ["concepts"]`, `num_c: 865`); `src/1_data_preprocessing/preprocess_XES3G5M.py` |
| Re-truncation | Test only: every sequence column cut to its **first 200** entries, written to `test_sequences.csv`. Train is the dataset's own 200-row windows | `preprocess_XES3G5M.py`, `shortest_len = 200` |
| Timestamps | Present in the CSVs, dropped by `KTDataset` (DKT does not use them) | `pykt/datasets/data_loader.py` |
| Filters | None in preprocessing. `KTDataset` applies `min_seq_len: 3` | `data_config.json` |
| Dedup of repeats | **None.** Same-batch duplicates and cross-batch re-attempts are both present in train and test as the model sees them | — |
| Multi-KC questions | Expanded into one row per KC by the KC-level files (the dataset's `is_repeat` column marks continuation rows) | dataset release |
| Outputs | `./data/XES3G5M/test_sequences.csv`, `./data/XES3G5M/test_question_window_sequences.csv`; pyKT writes `.pkl` caches beside them | — |
| `selectmasks` for test | Built by `transform_string`: `-1` → `-1`, else `1` (if the row contains both 0 and 1) | `preprocess_XES3G5M.py` |

**Where the data must live:** directly at `../ktcf-work/data/XES3G5M/` (contents of the release's `kc_level/` plus `metadata/`; the release's `metadata/embeddings/` and `metadata/images/` come along but are unused). The folder must be writable for pyKT's pickle cache (`test_sequences.csv_-1.pkl` etc.), so it is a copy, not a symlink to `data/raw/`.

**Consequences for Study 1**
- KTCF-preprocessed data cannot be used for the audit (KC-expanded, truncated, undeduplicated). The audit uses `data/processed/xes3g5m_clean.parquet`, built from the question-level files.
- KTCF's DKT is **concept-level**: it never sees question identity. A re-attempt of question *q* is, to this model, just another interaction on *q*'s KC. This is the model family 1 ("concept-level, no forgetting") of the pre-registration and bounds what it can possibly know about re-attempts.
- KTCF's model was trained with the ~1% same-batch duplicates present. Our Phase 4 retraining removes them; both numbers are reported.
- KTCF's evaluation population is the first 200 KC-level interactions of each test student, further filtered (see §4). Our calibration test uses full test sequences from the clean table.

## 3. Student model (DKT)

| | Paper | Checkpoint `saved_model/qid_model.ckpt` (2026-10-27) | Retrained by us |
| --- | --- | --- | --- |
| Config | DKT via pyKT, “setups identical to pyKT”; no sizes given | DKT, emb/hidden 200, dropout 0.2, lr 1e-3, Adam, batch 256, **10 epochs**, seed 42, fold 0 (`saved_model/config.json`) | not needed |
| Level | concept | concept (`emb_type qid`, `num_c 865`) | |
| Test AUC | 0.8226 | **0.8226** (`test_sequences.csv`: 3,613 students, 718,987 scored positions) | |
| Test ACC | 0.8253 | **0.8252** | |
| Window AUC / ACC | not reported | 0.7745 / 0.8153 (`test_question_window_sequences.csv`: 697,697 windows, 1,270,391 positions) | |
| Loaded cleanly | | yes, after P0 (`map_location="cpu"`) | |

Command: `cd ../ktcf-work && uv run --project ../kt-recourse-calibration python src/2_dkt_training_eval/wandb_predict.py --use_wandb 0 --save_dir saved_model`. CPU, ~15 min including pickle cache build.

Note `kt_config.json` says 50 epochs and dropout 0.1; the shipped checkpoint was trained with 10 epochs and dropout 0.2 (CLI defaults in `wandb_dkt_train.py`). The checkpoint's config is authoritative.

## 4. Counterfactual search (Table 1 comparison)
**Pipeline.** `dkt_inference.py` loads the checkpoint, runs the KC-level test loader, and for each student keeps the **last** position where `response == 0` and `prediction < 0.5` as `target_timestep` (students with no such position are dropped). Output `XES3G5M_test_predictions.csv`; then filtered to students whose response sequence is **≥ 45% zeros** → `XES3G5M_test_predictions_45_zeros.csv`. `run.py` samples **200** of these with `random_state=42` and runs one algorithm (`ktcf`, `wachter`, `dice`).

**Evaluation population (run 2026-10-27).** 3,613 test students → **3,456** with a valid target (157 removed: no position both answered wrong and predicted wrong) → **253** with ≥ 45% wrong (7.0% of the test set) → **200** sampled, i.e. 79% of the eligible pool. Target position: median 176 of 199, min 0, max 198. Table 1 therefore describes a narrow, low-performing slice of students with late targets and many wrong answers available to flip; it is not a statement about the typical student. Our calibration study uses all repeat events in the full clean test set, a different and much broader population; the write-up must say so.

Note: the prediction CSVs store sequences via `np.array2string`, which wraps long arrays across lines inside a cell; `wc -l` over-counts rows by ~80×. Count rows with pandas.

**Known code facts to state**
1. `run.py` lines 153–154: `if idx == 1: break`. As shipped the script evaluates one instance. Removed by patch `P1` for the reproduction.
2. In `KTCF.generate_cf_dkt`, `loss_prox` is `scipy.spatial.distance.hamming(...)` (a Python float) and `loss_kc` is a Python float from `get_kc_loss`. Neither carries a gradient; `total_loss.backward()` updates `cf_r` through `loss_pred` only. The prox and KC terms influence the printed loss and the `early_stopping_eta` convergence check, not the search direction. Check this against the paper's description before characterizing it further.
3. The mask `original_r == 0` means only originally-wrong positions can change; originally-correct answers are restored after every step, so "actionability" violations (1 → 0 flips) can only come from the initialization noise, not the optimizer.
4. Validity thresholds raw `cf_r`'s prediction at the target (`> 0.5`); sparsity and KC distance threshold `sigmoid(cf_r) > 0.5`. Under the default `init_scheme 1` (original + N(0, 0.1) noise, no sigmoid in the forward pass) these two views of the same `cf_r` can disagree. Check on a hand-inspected instance.
5. `target_proba = 1.0`; BCE against 1.0, not against the 0.5 validity threshold.

**Metrics (`eval_metrics.py`)**
- Validity: `pred_at_target > 0.5` (for DiCE, all 3 counterfactuals must pass).
- Sparsity: number of positions where `sigmoid(cf_r) > 0.5` differs from `original_r`; sparsity rate divides by sequence length (200).
- KC distance: mean over changed positions of the shortest-path length (unweighted, undirected KC graph) from the changed interaction's KC to the target's KC; from `shortest_paths.pkl`.
- Actionability: number of positions flipped **1 → 0** (lower is better); actionability rate divides by sparsity.
- Time: wall seconds per instance.

**Defaults (`run.py` argparse):** `init_scheme 1`, `lr 0.01`, `max_iter 200`, `init_noise_std 0.1`, `lambda_pred 1.0`, `lambda_prox 0.1`, `lambda_kc 0.001`, `early_stopping_eta 1e-4`.

**Results (2026-10-27, 200 students, seed 42, CPU; `results/table_1_results.csv`, copied to `docs/exploration/2026-10-27_table_1_results.csv`; logs beside it).** Paper values are Table 1 rows KTCF-rn, Wachter-rand, DiCE-rand. Baselines run with `--init_scheme 2` (random binary, the paper's `-rand`).

| Method | Metric | Paper | Ours | Δ |
| --- | --- | --- | --- | --- |
| KTCF (`init_scheme 1`, lr 0.01) | validity | 0.930 ± 0.26 | **0.975 ± 0.16** | +0.045 |
| | sparsity / rate | 49.8 ± 8.4 / 0.250 ± 0.04 | 52.5 ± 9.2 / 0.264 ± 0.05 | +2.6 |
| | KC distance | not reported | 12.43 ± 2.75 | — |
| | actionability / rate | 0 / 0 | 0 / 0 | exact |
| | time | 3.02 ± 0.91 s | 6.33 ± 1.97 s | CPU |
| KTCF (lr 1e−4, the paper's η) | validity | — | 0.965 ± 0.18 | |
| | sparsity / rate | — | 54.0 ± 9.0 / 0.272 | |
| | time | — | 2.10 ± 0.82 s | early stop fires within a few steps |
| Wachter (`init_scheme 2`) | validity | 0.725 ± 0.45 | 0.705 ± 0.46 | −0.020 |
| | sparsity / rate | 67.4 ± 10.3 / 0.338 ± 0.05 | 67.2 ± 10.2 / 0.338 ± 0.05 | match |
| | actionability / rate | 40.5 ± 10.9 / 0.617 ± 0.20 | 40.2 ± 11.1 / 0.614 ± 0.20 | match |
| | time | 3.79 ± 0.08 s | 8.58 ± 0.20 s | CPU |
| DiCE (`init_scheme 2`) | validity | 0.880 ± 0.33 | 0.885 ± 0.32 | +0.005 |
| | sparsity / rate | 75.6 ± 14.7 / 0.380 ± 0.07 | 75.3 ± 14.6 / 0.379 ± 0.07 | match |
| | actionability / rate | 35.3 ± 12.2 / 0.504 ± 0.25 | 35.3 ± 12.2 / 0.506 ± 0.25 | match |
| | time | 2.57 ± 1.87 s | 4.34 ± 3.11 s | CPU |

**Reading.** Both baselines reproduce to ±0.02 on every metric, so data, checkpoint, sample, and metric code are identical to the paper's. KTCF reproduces within one SD, with validity 4.5 points higher and sparsity 2.6 higher.

**Learning-rate check.** The paper states η = 1e−4; the code default is 0.01. Running KTCF at lr 1e−4 leaves validity (0.965) and sparsity (54.0) essentially unchanged while runtime drops to 2.1 s because the early-stopping test (τ = 1e−4) triggers after a few near-zero-change steps. The lr discrepancy therefore does not explain the validity gap, and it shows something more important:

**The KTCF result is largely fixed at initialization, not by the optimizer.** Two mechanisms in the code account for it (to be confirmed by the diagnostic below before being stated as a finding):
1. Sparsity counts positions with `sigmoid(cf_r) > 0.5`, i.e. `cf_r > 0`. Under `init_scheme 1` (`cf_r = original + N(0, 0.1)`), roughly half of all originally-wrong positions receive positive noise and are counted as flipped at step 0. The sampled students have ~90–110 wrong answers in 199 positions; half of that is 45–55, matching both the paper's 49.8 and our 52–54.
2. Validity is evaluated on the raw continuous `cf_r` through the differentiable `soft_embedding`. A hundred positions nudged by ±0.1 can move the LSTM's target prediction past 0.5 with no position flipped in the binary sense. The certified counterfactual is a soft response vector no student could produce.

Because the outcome depends on the exact Gaussian draw, it is sensitive to the random stream, and `torch.randn` with the same seed differs between CPU and CUDA. The baselines use `torch.randint` with no actionability mask and are optimizer-driven, which is consistent with their tight reproduction. This is the working explanation of the KTCF gap.

**Diagnostic to run.** On the same 200 students, prediction at the target under (a) original responses, (b) `cf_r` at initialization, zero optimizer steps, (c) final `cf_r` as KTCF evaluates it, (d) final `cf_r` binarized (`sigmoid > 0.5`, mask re-applied). Validity rate under each. If (b) is already high and (d) ≪ (c), KTCF's validity metric does not measure whether the recommended corrections would change the model's prediction. Script: `src/audit/ktcf_validity_diagnostic.py`.

## 5. Deviations from the paper

1. CPU instead of CUDA; `torch.use_deterministic_algorithms(True)` kept. Expected effect: none on metrics, slower runtime column.
2. Patch P1 removes the one-instance `break`. Expected effect: this is what produces 200 instances at all.
3. `--use_wandb 0` everywhere. No effect.
4. All runs from `../ktcf-work` with `uv run --project ../kt-recourse-calibration`; `KTCF_ROOT=../ktcf-work` in `.env`.
5. Random streams differ between CPU and CUDA for the same seed. Baselines (`torch.randint`, mask-free, optimizer-driven) reproduce to ±0.02; KTCF (`torch.randn` noise, initialization-dominated) reproduces within one SD with validity +0.045.
6. Learning rate: paper η = 1e−4, code default 0.01. Both run; neither changes the KTCF result meaningfully (see §4).

## 6. Patches applied to KTCF code

Kept in `src/ktcf_patches/ktcf-work.patch`; rebuild instructions in `src/ktcf_patches/README.md`. `../ktcf` itself is never edited.

| ID | File | Change | Reason |
| --- | --- | --- | --- |
| P0 | `pykt/models/init_model.py:162` | `torch.load(..., map_location="cpu")` | checkpoint saved from CUDA tensors; no effect on numbers. Same call exists at `src/2_dkt_training_eval/wandb_train.py:163` (patch if retraining) |
| P1 | `src/run.py` | delete `if idx==1: break` | evaluate the sampled 200, not 1 |
| P2 | `src/run.py` | `test_predictions = ...sample(n=200, random_state=42)` → make `n` a CLI arg | subsample for quick checks |
| P3 | `src/2_dkt_training_eval/*.py`, `src/run.py` | `use_wandb` default 0 | no API key |


## 7. Verdict

**DKT checkpoint: reproduced exactly.** Test AUC 0.8226 / ACC 0.8252 vs. paper 0.8226 / 0.8253.

**Table 1: reproduced.** Wachter and DiCE within ±0.02 on every metric; KTCF within one SD, validity 0.045 higher. All qualitative claims hold: KTCF produces zero unactionable flips by construction of its mask; Wachter and DiCE flip 35–40 originally-correct answers to wrong; KTCF is sparser than both.

**Unresolved and important.** The lr sensitivity run indicates that KTCF's sparsity and validity are largely determined by the Gaussian initialization and the soft-embedding evaluation rather than by optimization. This is a property of the shipped code as run; the diagnostic in §4 decides whether it is a finding about the method. It is not yet to be stated as such outside this note.

**Scope caveat for everything above.** The Table 1 population is 200 of 253 test students who answered ≥ 45% of their first 200 KC-level interactions wrong, with targets at median position 176. Our calibration study uses all cross-batch repeat events in the full clean test set.

## 8. Open items for Phase 4

- Calibration hooks: `dkt_inference.py` already dumps per-timestep `y` for every test student; extend it to dump on the clean question-level test set (via a concept-level view) and on the full sequence, not the first 200.
- The counterfactual's per-flip predicted lift is not exposed; `cf_r` and `pred_at_target` are returned, so lift per intervention must be recomputed by re-running the model on single flips.
- The 0.5 validity threshold is hard-coded in `eval_validity`; `target_proba = 1.0` is a module constant in `cf_generator.py`.
- Model family 1 is concept-level by construction. The question-aware and forgetting-aware families (pre-registration §5) need upstream `pykt-toolkit`, since KTCF's vendored copy ships only `dkt.py`.

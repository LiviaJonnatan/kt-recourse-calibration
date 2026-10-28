# KTCF reproduction

Reference: Kim, Lee, Kim. *KTCF: Actionable Recourse in Knowledge Tracing via Counterfactual Explanations for Education.* AAAI 2026 (AI for Social Impact track, oral). arXiv 2601.09156. Code: https://github.com/woojinkim1021/ktcf, commit `a96906afa7525b60e1847284d0a2db13685cc670` (4 commits, no releases, no licence file).

Our commit at the time of this reproduction: `786f553c550a9fdd74839f121ad6f2d1d9205a9d`.

## 1. Environment

| Package | KTCF `requirements.txt` | Ours | Note |
| --- | --- | --- | --- |
| Python | 3.12.11 | 3.12 | |
| torch | 2.7.1+cu128 | 2.14.1 | CUDA wheel dropped; CPU/MPS build |
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

**Results (2026-10-27, 200 students, seed 42, CPU; `results/table_1_results.csv` copied to `docs/exploration/`; one log per run beside it).** Paper rows and the code's `init_scheme`: KTCF-rn = 1 (Gaussian noise, eq. 10), -rand = 2 (random binary, eq. 11), -sr = 3 (soft relaxation, eq. 12), -cc = 4 (convex combination, eq. 13, λ_cc = 0.5), -gs = 5 (Gumbel-sigmoid, eq. 14, `init_temp` 0.1). Baselines use scheme 2.

| Row | Metric | Paper | Ours | Δ |
| --- | --- | --- | --- | --- |
| Wachter-rand | validity | 0.725 ± 0.45 | 0.705 ± 0.46 | −0.020 |
| | sparsity / rate | 67.4 ± 10.3 / 0.338 | 67.2 ± 10.2 / 0.338 | match |
| | actionability / rate | 40.5 ± 10.9 / 0.617 | 40.2 ± 11.1 / 0.614 | match |
| | time | 3.79 ± 0.08 s | 8.58 ± 0.20 s | CPU |
| DiCE-rand | validity | 0.880 ± 0.33 | 0.885 ± 0.32 | +0.005 |
| | sparsity / rate | 75.6 ± 14.7 / 0.380 | 75.3 ± 14.6 / 0.379 | match |
| | actionability / rate | 35.3 ± 12.2 / 0.504 | 35.3 ± 12.2 / 0.506 | match |
| | time | 2.57 ± 1.87 s | 4.34 ± 3.11 s | CPU |
| KTCF-rn | validity | 0.930 ± 0.26 | **0.975 ± 0.16** | +0.045 |
| | sparsity / rate | 49.8 ± 8.4 / 0.250 | 52.5 ± 9.2 / 0.264 | +2.6 |
| | time | 3.02 ± 0.91 s | 6.33 ± 1.97 s | CPU |
| KTCF-rand | validity | 0.720 ± 0.45 | 0.765 ± 0.43 | +0.045 |
| | sparsity / rate | 54.0 ± 9.2 / 0.271 | 54.1 ± 9.3 / 0.272 | match |
| | time | 4.70 ± 0.06 s | **0.12 ± 0.01 s** | early stop on step 1–2 in every instance; unexplained (paper's tiny SD implies `max_iter` every time) |
| KTCF-sr | validity | 0.930 ± 0.26 | 0.950 ± 0.22 | +0.020 |
| | sparsity / rate | 50.1 ± 7.7 / 0.252 | 53.9 ± 9.0 / 0.271 | +3.8 |
| | time | 3.07 ± 1.15 s | 5.26 ± 2.25 s | CPU |
| KTCF-cc | validity | 0.685 ± 0.47 | 0.690 ± 0.46 | +0.005 |
| | sparsity / rate | 55.6 ± 8.3 / 0.280 | 54.1 ± 9.3 / 0.272 | −1.5 |
| | time | 3.77 ± 0.97 s | 6.13 ± 1.67 s | CPU |
| KTCF-gs | validity | 0.920 ± 0.27 | 0.925 ± 0.26 | +0.005 |
| | sparsity / rate | 49.9 ± 7.7 / 0.251 | 53.9 ± 9.0 / 0.271 | +3.9 |
| | time | 2.20 ± 1.52 s | 4.88 ± 2.14 s | CPU |
| KTCF, all five | actionability / rate | 0 / 0 | 0 / 0 | exact |
| KTCF, all five | KC distance | not reported | 12.19–12.43 | — |
| KTCF-rn, lr 1e−4 | validity / sparsity / time | — | 0.965 / 54.0 / 2.10 s | lr check, see below |

**Reading.** All seven rows reproduce. Baselines match to ±0.02 on every metric; the five KTCF validities are within 0.045 of the paper with the paper's ordering preserved exactly (rn ≈ sr > gs > rand > cc); actionability is zero on every KTCF row. Sparsity: the hard-start rows (rand, cc) match to 0.2; the soft-start rows (rn, sr, gs) are ~4 higher than the paper's, meaning the paper's optimizer moved ~4 flips where ours moved ~1.5, a device-numerics difference in the Adam path that cannot be resolved without their GPU and changes no conclusion.

**KTCF-rand and KTCF-cc are the same flip set.** Both rows show sparsity 54.145 and KC distance 12.187050 to six decimals. With λ_cc = 0.5 the convex start is `0.5·z` on wrong positions, which thresholds (`sigmoid > 0.5`, i.e. `> 0`) to exactly the flips of `z`, and the optimizer never changes them. Only the soft values fed to the model differ (0.5 vs 1), giving 0.690 vs 0.765 validity. Initialization dominance shown across two schemes without a diagnostic.

**Learning-rate check.** The paper states η = 1e−4; the code default is 0.01. Running KTCF at lr 1e−4 leaves validity (0.965) and sparsity (54.0) essentially unchanged while runtime drops to 2.1 s because the early-stopping test (τ = 1e−4) triggers after a few near-zero-change steps. The lr discrepancy therefore does not explain the validity gap, and it shows something more important:

**Validity diagnostic (`src/audit/ktcf_validity_diagnostic.py`, run 2026-10-27, same 200 students; per-student CSV and log in `docs/exploration/`).** The script reproduces the Table 1 run exactly ((a) = 0.000, (c) = 0.975) and then re-evaluates the model's prediction at the target under alternative views of the same counterfactual.

| Condition | What the model is given | Validity (pred > 0.5) |
| --- | --- | --- |
| a | original responses | 0.000 |
| b | `cf_r` at initialization, noise on all positions, zero optimizer steps | 0.085 |
| b_m | initialization with the actionability mask (noise on wrong answers only), zero steps | **0.375** |
| c | final continuous `cf_r`, as `eval_validity` uses it | **0.975** (= Table 1) |
| d | final `cf_r` binarized by `sigmoid > 0.5` (the `eval_sparsity` rule), mask re-applied | **0.765** |
| d2 | final `cf_r` binarized by `cf_r > 0.5` (the rule inside the optimizer loop), mask re-applied | 0.000 |

Sparsity: 54.0 at initialization, 52.5 final (Table 1: 52.5), against a mean of 108.5 wrong answers per student (half: 54.2). Under the in-loop `> 0.5` rule, final sparsity is 0. Soft-embedding index drift: 107.9 of 199 positions at initialization, 108.1 at the end. `cf_r` range over all instances: [−0.42, 1.00].

**What this shows, as implemented in the released code on the released checkpoint and sample:**

1. *Sparsity is set by the initialization noise, not the optimizer.* Half of each student's wrong answers receive positive Gaussian noise and are counted as flipped at step 0 (54.0 ≈ 108.5 / 2); 200 Adam iterations change this by ~1.5 positions.
2. *The optimizer never produces a correct answer by its own criterion.* No position ever reaches `cf_r > 0.5`, so the proximity term the paper describes is identically zero throughout (and, separately, carries no gradient because it is a scipy float). The ~52 "flips" that `eval_metrics` counts are positions with `cf_r ∈ (0, 0.5)`.
3. *The model evaluates a different student.* `dkt.py` computes the interaction index as `q + num_c · r` and `soft_embedding` interpolates across that flattened index, so a wrong answer on concept *q* with `cf_r = 0.3` is embedded as concept *q + 259* answered wrong, not as *q* partly corrected. Every position the optimizer may touch (108 of 199) is looked up as an unrelated concept. The sequence certified 97.5% valid is the student with every mistake replaced by a different concept answered wrong. KC coherence is undefined for this input.
4. *The actionable recommendation is valid 76.5% of the time, not 97.5%.* Binarizing the flagged positions into real corrections (d) and re-asking the model is the only step in the pipeline that evaluates something a student could do; reported validity overstates it by 21 points on this population.

Initialization alone (b_m) already yields 37.5% validity, so the optimizer does contribute, but on inputs that have no interpretation as corrections. Phrase all of this as a property of the released implementation; the paper's text may describe an intended method the code does not realize. The authors should be informed before this appears in any write-up.

**Consequences for Study 1.** RQ3 adds a required condition: KTCF validity evaluated on binarized recommendations, and all "counterfactual lift" quantities are computed on binarized interventions against observed post-correction outcomes.

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

**Established by the diagnostic (§4).** As released, KTCF's reported sparsity is fixed by its initialization noise, its proximity term is identically zero, its optimizer operates on inputs the model embeds as different concepts, and its actionable (binarized) validity is 0.765 against a reported 0.975. These are reproducible properties of the code on the paper's own model and sample. They are stated here as implementation facts and should be put to the authors before being characterized further.

**Scope caveat for everything above.** The Table 1 population is 200 of 253 test students who answered ≥ 45% of their first 200 KC-level interactions wrong, with targets at median position 176. Our calibration study uses all cross-batch repeat events in the full clean test set.

## 8. Open items for Phase 4

- Calibration hooks: `dkt_inference.py` already dumps per-timestep `y` for every test student; extend it to dump on the clean question-level test set (via a concept-level view) and on the full sequence, not the first 200.
- The counterfactual's per-flip predicted lift is not exposed; `cf_r` and `pred_at_target` are returned, so lift per intervention must be recomputed by re-running the model on single flips.
- The 0.5 validity threshold is hard-coded in `eval_validity`; `target_proba = 1.0` is a module constant in `cf_generator.py`.
- Model family 1 is concept-level by construction. The question-aware and forgetting-aware families (pre-registration §5) need upstream `pykt-toolkit`, since KTCF's vendored copy ships only `dkt.py`.

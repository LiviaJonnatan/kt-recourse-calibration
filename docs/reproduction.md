# KTCF reproduction

Reference: Kim, Lee, Kim. *KTCF: Actionable Recourse in Knowledge Tracing via Counterfactual Explanations for Education.* AAAI 2026 (AI for Social Impact track, oral). arXiv 2601.09156. Code: https://github.com/woojinkim1021/ktcf, commit `a96906afa7525b60e1847284d0a2db13685cc670` (4 commits, no releases, no licence file).

Our commit at the time of this reproduction: `786f553c550a9fdd74839f121ad6f2d1d9205a9d` (Table 1); diagnostic section updated at `038f608`+ (2026-10-31).

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
4. Validity thresholds the model's prediction on the final *continuous* `cf_r` (`> 0.5`); sparsity and KC distance threshold `sigmoid(cf_r) > 0.5`, i.e. the sign of `cf_r`. The two metrics therefore describe different vectors: validity is scored on a soft history, sparsity on a 0/1 one. Confirmed on all five schemes by the diagnostic below.
5. `target_proba = 1.0`; BCE against 1.0, not against the 0.5 validity threshold.
6. `cf_generator.py` forward pass is written `if scheme == 3: y = model(q, sigmoid(cf_r))` / `if scheme == 5: y = model(q, gumbel-sigmoid(cf_r))` / `else: y = model(q, cf_r)`. The `else` binds to the second `if`, so for scheme 3 the sigmoid forward pass is computed and immediately overwritten by the raw one. KTCF-sr therefore feeds the model raw Gaussian logits (range ≈ ±4), not `σ(z)` as eq. 12 states; its `loss_prox` and `loss_kc` do use `sigmoid(cf_r)`. Reproduction keeps this as released.
7. Schemes 3 (sr) and 5 (gs) share the same initialization, `cf_r = randn` (`init_cf.py`); with a fixed seed they start from the identical vector. gs differs only in the forward transform `sigmoid((cf_r + g1 − g2) / init_temp)`, where `g1`, `g2` are two **scalars** sampled once per `KTCF` object (`sample_gumbel(1)`), not per-element Gumbel noise as eq. 14 reads. With `init_temp = 0.1` the transform is a near-step function at `cf_r = g2 − g1` (= 0.467 for seed 42).
8. Under gs the transform is applied to the whole vector after the mask projection, including the originally-correct positions reset to exactly 1: `σ((1 − 0.467)/0.1) = 0.9952`, which `soft_embedding` indexes at `q + 865·0.9952` → row `q + 860`, i.e. concept `q − 5` answered right. Under gs the model never sees the student's correct answers on their own concept either.
9. Code fact 2 applies to every scheme: the sparsity term is a thresholded Hamming distance in all five branches, so `lambda_prox` has no effect on the search in any configuration.

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

**Validity diagnostic (`src/audit/ktcf_validity_diagnostic.py --init_scheme N`, run 2026-10-31, same 200 students, all five schemes; one CSV and one log per scheme in `docs/exploration/`).** The script calls KTCF's own `initialize_response` and `generate_cf_dkt` with the Table 1 parameters and seed, then re-asks the model for its prediction at the target under alternative views of the same `cf_r`. Soft vectors are passed through the same per-scheme transform the generator applies before its forward pass (identity for schemes 1–4, including sr per code fact 6; the Gumbel-sigmoid for scheme 5), so condition (c) reproduces Table 1 validity for every scheme.

| Condition | What the model is given |
| --- | --- |
| a | original responses (sanity: must be 0.000 by construction of the sample) |
| b | `cf_r` at initialization, noise on all positions, zero optimizer steps |
| b_m | initialization with the actionability mask applied (noise on wrong answers only), zero steps |
| c | final continuous `cf_r`, transformed as the generator transforms it; this is what `eval_validity` scores |
| d | final `cf_r` binarized by the generator's own sparsity rule (`sigmoid(cf_r) > 0.5` for schemes 1–4; transformed value `> 0.5`, i.e. `cf_r > g2 − g1`, for gs), mask re-applied; every entry 0/1 |
| d2 | final `cf_r` binarized by `cf_r > 0.5`, mask re-applied |

| | rn | rand | sr | cc | gs |
| --- | --- | --- | --- | --- | --- |
| a | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| b | 0.085 | 0.470 | 0.520 | 0.025 | 0.055 |
| b_m | 0.375 | 0.765 | 0.785 | 0.170 | 0.440 |
| **c** (Table 1 validity) | **0.975** | **0.765** | **0.945** | **0.700** | **0.925** |
| generator's own value | 0.975 | 0.765 | 0.950 | 0.690 | 0.925 |
| **d** (binarized) | **0.765** | **0.765** | **0.760** | **0.765** | **0.550** |
| d2 | 0.000 | 0.765 | 0.525 | 0.440 | 0.530 |
| sparsity, init → final (d rule) | 54.0 → 52.5 | 54.1 → 54.1 | 54.0 → 53.9 | 54.1 → 54.1 | 34.9 → 34.9 |
| sparsity, final (d2 rule) | 0.0 | 54.1 | 33.6 | 27.1 | 33.7 |
| index drift, init → final (of 199) | 107.9 → 108.1 | 0.0 → 0.0 | 108.3 → 108.3 | 54.1 → 54.1 | 61.0 → 154.0 |
| `cf_r` range, all instances | [−0.42, 1.00] | [0.00, 1.00] | [−4.22, 4.33] | [0.00, 1.00] | [−4.22, 4.33] |

Mean wrong answers per student: 108.5 (half: 54.2). (c) differs from the generator's value by 1–2 students for sr and cc; the generator reports the prediction from its last forward pass, which precedes that iteration's mask projection, whereas (c) scores the returned `cf_r`. Under gs, (b_m) keeps the correct positions at exactly 1, whereas the generator transforms them to 0.9952 on every iteration after the first (code fact 8); (b) and (c) are vectors the generator literally evaluated, (b_m) is a reconstruction.

**What this shows, as implemented in the released code on the released checkpoint and sample:**

1. *Which answers are "flipped" is decided by the sign of the initial random draw, in every scheme.* Sparsity under each scheme's own rule is unchanged, to within 1.5 positions, between step 0 and step 200. For rn, sr and cc it is half of the wrong answers (the draw is symmetric about the threshold); for gs it is the ~32% of draws above 0.467. No scheme's optimizer moves a position across its threshold in either direction at any appreciable rate; `cf_r` under rand is unchanged to within 1/865 (no lookup changes).
2. *The paper's validity is scored on a history the student does not have.* `dkt.py`'s `soft_embedding` indexes `q + 865·cf_r`; any non-integer value is looked up on another concept's row. Drift is ~108 of 199 positions (every wrong answer) for rn and sr, 54 for cc (the positions that drew 0.5), 0 for rand, and 154 for gs (every wrong answer plus every correct answer, code fact 8). The Table 1 ordering of initializations (rn ≈ sr > gs > rand > cc) tracks how far off-grid each scheme's final vector is, not anything about the recommendation.
3. *Binarized validity is a function of how many random wrong answers are flipped, and of nothing else.* Across the five schemes and both binarization rules, (d)/(d2) against mean flips: 0 flips → 0.000 (rn, d2); 27 → 0.440 (cc, d2); 34 → 0.525–0.550 (sr d2, gs d, gs d2); 52–54 → 0.760–0.765 (rn, rand, sr, cc under d). Which scheme generated the flips does not enter.
4. *The actionable recommendation validates at 0.76, or 0.55 under gs, against reported 0.92–0.975.* For rand the two coincide because there is no drift to remove. For every soft scheme the gap is the model's response to drift, not to corrections.
5. *The optimizer contributes to (c) only by moving drifted lookups to other drifted lookups.* cc is the clearest case: (b_m) 0.170 → (c) 0.700 while drift (54.1) and flips (54.1) are both unchanged; the 0.5-valued positions were nudged to 0.5 ± ε, i.e. from one unrelated concept's row to a neighbouring one.

Phrase all of this as a property of the released implementation. The paper's text may describe an intended method the code does not realize. The authors should be informed before this appears in any write-up.

**Consequences for Study 1.** RQ3 adds a required condition: KTCF validity evaluated on binarized recommendations (condition d, per scheme), and all "counterfactual lift" quantities are computed on binarized interventions against observed post-correction outcomes. The "random half of wrong answers" baseline (condition d under rand) is the reference point any recourse method must beat.

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

**Established by the diagnostic (§4), all five initializations.** As released, which answers KTCF recommends is fixed by the sign of its initialization draw and unchanged by the optimizer; its sparsity term carries no gradient; its reported validity is scored on a continuous vector that `soft_embedding` looks up as other concepts (every wrong answer under rn/sr, every position under gs); and the validity of the 0/1 recommendation is 0.76 for rn, rand, sr and cc and 0.55 for gs, against reported 0.70–0.975. Binarized validity depends only on the number of randomly flipped wrong answers. These are reproducible properties of the code on the paper's own model and sample, stated here as implementation facts to be put to the authors before being characterized further.

**Scope caveat for everything above.** The Table 1 population is 200 of 253 test students who answered ≥ 45% of their first 200 KC-level interactions wrong, with targets at median position 176. Our calibration study uses all cross-batch repeat events in the full clean test set.

## 8. Open items for Phase 4

- Calibration hooks: `dkt_inference.py` already dumps per-timestep `y` for every test student; extend it to dump on the clean question-level test set (via a concept-level view) and on the full sequence, not the first 200.
- The counterfactual's per-flip predicted lift is not exposed; `cf_r` and `pred_at_target` are returned, so lift per intervention must be recomputed by re-running the model on single flips.
- The 0.5 validity threshold is hard-coded in `eval_validity`; `target_proba = 1.0` is a module constant in `cf_generator.py`.
- Model family 1 is concept-level by construction. The question-aware and forgetting-aware families (pre-registration §5) need upstream `pykt-toolkit`, since KTCF's vendored copy ships only `dkt.py`.

## Study 2 — uplift-objective recourse

**What was run.** `src/uplift/` stages 0–8 on XES3G5M (KTCF's released DKT checkpoint, no
retraining), Duolingo SLAM en_es, and ASSISTments 2012-13 (skill-tagged original problems); three
seeds, 20 bootstrap refits, three outcomes (next-5 same-area, same-item next encounter, next-20
same-area), with and without a headroom filter (recent same-area accuracy < 0.8); new-practice policy
and review-timing analyses; set-level selection on XES3G5M and SLAM. Commands in `src/uplift/README.md`.

**Invariants hit.**
- XES3G5M: 5,491,578 clean interactions, 183,806 re-attempts (same as `reconstruct_log.json`);
  released DKT 0.7765 AUC on full cleaned test sequences (0.7745 on the window file; 0.8226 on the
  truncated 200-step file, as published).
- SLAM: 3,396,935 tokens, 2,593 learners, 73.3% re-attempts; GBM student model 0.7993 AUC
  (shared-task logistic baseline 0.774).
- ASSISTments: 2,533,720 problems, 18,180 students, 4.9% same-problem re-attempts; GBM student
  model 0.754 AUC (DKT-Forget published ≈ 0.73).
- HLR fit on Duolingo traces (en learners / es UI, 1.5M rows): MAE 0.140 vs 0.173 constant
  (paper: 0.128 vs 0.175).

**What reproduced exactly across machines (sandbox → laptop).** Stage 1 counts, stage 2 AUCs,
T-learner and LCB top-20% gains to three decimals, average-effect estimates, four-group shares.

**What varied.** DR-learner top-20% gains on the review arm (XES3G5M: +0.050 sandbox vs +0.018
laptop at seed 0; seed sd up to 0.079 on ASSISTments). Cause: inverse-propensity weights in the
pseudo-outcome. Decision: τ_LCB is the reported estimator; τ_DR is a debiasing check only.

**Sandbox vs laptop settings.** Sandbox: 8 bootstraps, 200k treated cap, 300–600 students at set
level. Laptop (results of record): 20 bootstraps, 300k treated cap, 3 seeds, 1,000 students.

**Student-model ablation (pyKT, one seed).** Export via `s13_pykt_export.py` (200-step chunks, −1 padding,
timestamps in seconds); pyKT 0.x in a Python 3.12 venv (scipy from a Python 3.10 standalone build failed to
load on macOS; `tqdm`, `einops`, `wandb` had to be installed by hand; `data_config.json` needs the full
entry incl. `folds`). Validation AUC from pyKT: SLAM DKT-Forget 0.757; ASSISTments DKT 0.725, DKT-Forget
0.728. AUC on our evaluation rows via `s14_pykt_predict.py`: SLAM DKT 0.7495, DKT-Forget 0.7407;
ASSISTments DKT 0.7285, DKT-Forget 0.7312. `s14` strips training hyperparameters from pyKT's
`model_config` before `init_model`, reads the concept map with `dtype=str` (ASSISTments skill ids), and
mirrors pyKT's `calC` gap discretisation (`round(log2(t+1))`, `+1` on gaps, none on counts).

**Corrections made during the study** are listed in `docs/uplift/RESULTS.md`.
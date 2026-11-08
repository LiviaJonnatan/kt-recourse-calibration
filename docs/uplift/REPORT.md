# Uplift-objective recourse for knowledge tracing: first full run on XES3G5M

Run date 2026-11-05. Everything here is produced by the five scripts in `src/` from the
XES3G5M question-level release, `questions.json`, and KTCF's released DKT checkpoint.
No retraining, no synthetic data. One CPU, ~40 minutes end to end.

## 0. The question

> For a student at this moment, which small set of past questions (k = 5, at most one
> per concept area), if re-attempted now, gives the largest causal lift on their
> correctness over their next 5 questions in that concept area, compared with doing a
> new question there, and can that lift be verified from what logged students actually did?

## 1. Pipeline and what each stage produced

| Stage | Script | Output | Check |
|---|---|---|---|
| 1 Event table | `s1_events.py` | 5,491,578 clean interactions; 183,806 repeats (3.35%: 136,631 reviews, 47,175 corrections); 53 level-2 areas; 4.13M events with a next-5 same-area outcome | matches `reconstruct_log.json` in kt-recourse-calibration exactly |
| 2 Student model | `s2_dkt.py` | KTCF's `qid_model.ckpt` loaded without PyTorch, LSTM forward in NumPy; P(correct) for every train/test row | test AUC 0.7765 / ACC 0.8146 on full cleaned sequences (repo: 0.7745 / 0.8153 on the window file; 0.8226 on the truncated 200-step file) |
| 3 Uplift model | `s3_uplift.py` | per arm (correction, review): propensity, T-, X-, DR-learner, 8 student-bootstrap refits; 2-fold cross-fit by student; train folds only | see §2 |
| 4 Selector | `s4_select.py` | 300 test students, random decision point, candidates = distinct past questions in last 60 positions, k = 5, 8 selectors | §4 |
| 5 Evaluation | `s5_event_eval.py`, `metrics.py` | Qini / uplift@20% on held-out events; per-set DR lift, evaluability, DKT-simulated validity, realized outcomes | §3, §4 |

Covariates are dataset-agnostic by design (no question or KC ids): `pre_area, pre_all,
hist, n_area, difficulty, single, p_dkt` shared; `gap_log, n_attempt` for the treated arm.

## 2. Average effects: naive vs debiased (train folds)

| Arm | n treated | naive ATE | DR ATE | mean propensity of treated |
|---|---|---|---|---|
| correction | 23,290 | −0.073 | −0.016 | 0.36 |
| review | 66,368 | +0.032 | −0.012 | 0.47 |

Test split (IPW): correction −0.089 naive → −0.065; review +0.024 naive → +0.005.

Reading: students who re-attempt a wrong answer are weaker than those who move on, and
students who re-do a right answer are stronger. Most of the raw "effect" of each action is
who does it. After debiasing, both population averages are within ±0.02 of zero. Any value
has to come from *heterogeneity*, which is what the next table tests.

## 3. Ranking signal: does the model know which re-attempts help? (held-out test events)

Observed next-5 gain, treated minus control, inside the top 20% of each ranker's ordering.
Controls are new-question events sampled 5:1 within area. "ipw" reweights by the
propensity model. Random and the ATE are the floor; positive numbers in the top-20% mean
the ranker found re-attempts that beat moving on.

| ranker | correction: top-20% gain | (ipw) | review: top-20% gain | (ipw) | Qini (corr / rev) |
|---|---|---|---|---|---|
| random | −0.097 | −0.082 | +0.022 | 0.000 | 0 / −3 |
| **p_dkt** (predicted correctness, KTCF's signal) | −0.081 | −0.033 | −0.010 | +0.008 | 114 / −200 |
| mu1 (predicted success after action) | −0.029 | −0.032 | −0.001 | +0.002 | 142 / −169 |
| easiest first | −0.124 | −0.076 | +0.001 | +0.027 | 68 / −94 |
| tau_T (T-learner) | +0.029 | +0.025 | **+0.068** | +0.030 | 126 / 220 |
| tau_X | −0.011 | +0.011 | +0.023 | +0.025 | 34 / 55 |
| **tau_DR** | **+0.061** | **+0.099** | +0.050 | +0.028 | **277 / 286** |
| tau_LCB (tau_T − 1·sd) | +0.019 | +0.028 | +0.049 | +0.010 | 112 / 161 |

(`neg_gap` is omitted: controls have gap 0, so it only sorts treated vs control.)

Findings
1. **The uplift objective beats the predicted-correctness objective on both arms.**
   For corrections the sign flips: KTCF's signal picks re-attempts that are 3–8 points
   *worse* than moving on; tau_DR picks ones that are 6–10 points *better*. For reviews
   predicted correctness is indistinguishable from random; tau_T/tau_DR find a +5 to +7
   point subgroup.
2. **Debiasing matters.** tau_DR > tau_T > tau_X on Qini for both arms; on the IPW
   curve the gap widens (correction +0.099 vs +0.025). The raw-gain model your teammate
   has is tau_T: it works, but a third to a half of its signal on corrections is selection.
3. **tau_DR calibration.** By decile of predicted lift, observed gain rises monotonically
   from −0.17 (lowest) to the top decile; the top review decile predicts +0.056 and
   observes +0.37 (n = 8,749). Magnitudes are under-predicted at the top and the DR
   pseudo-outcome has heavy tails (1st/99th pct −0.64 / +1.16 on observed events), so
   tau_DR is a good *ranker* and a poor *value estimate*. See §4 for the consequence.
4. **Four-group breakdown of logged re-attempts** (mu0, mu1 thresholds 0.2 / 0.8):
   corrections 14% persuadable, 22% sure things, 9% sleeping dogs; reviews 2.5%
   persuadable, 64% sure things, 7% sleeping dogs. Almost every logged review is of
   something the student already knows.

## 4. Chosen sets: 300 students, k = 5

| selector | n | tau_T of set | mu0 | mean e | evaluability (e ≥ .02) | DKT flip-valid | DKT append P | realized share | corr / rev | difficulty | gap (log10 s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| random | 5.0 | −0.008 | 0.78 | 0.10 | 0.67 | 0.91 | 0.82 | 0.4% | 1.1 / 3.9 | 0.21 | 5.96 |
| dkt_pcorrect | 5.0 | −0.010 | 0.83 | 0.13 | 0.69 | 0.90 | 0.81 | 0.8% | 0.7 / 4.3 | 0.14 | 5.34 |
| ktcf_flip (one-flip, corrections only) | 4.4 | −0.015 | 0.76 | 0.07 | 0.51 | **0.96** | 0.82 | 1.0% | 4.6 / 0 | 0.31 | 5.45 |
| raw_gain (tau_T) | 5.0 | **+0.043** | 0.76 | 0.10 | 0.68 | 0.92 | 0.82 | 0.3% | 0.9 / 4.1 | 0.20 | 5.86 |
| uplift_dr | 5.0 | −0.005 | 0.78 | **0.02** | **0.27** | 0.90 | 0.81 | 0.0% | 0.9 / 4.1 | 0.15 | 6.28 |
| uplift_lcb | 5.0 | +0.041 | 0.77 | 0.10 | 0.69 | 0.92 | 0.82 | 0.5% | 0.9 / 4.1 | 0.20 | 5.80 |
| + one per area | 4.9 | +0.027 | 0.78 | 0.10 | 0.63 | 0.91 | 0.81 | 0.7% | 0.9 / 4.0 | 0.20 | 5.79 |
| + support filter (full) | 4.7 | +0.021 | 0.78 | **0.14** | **1.00** | 0.91 | 0.82 | 0.7% | 0.9 / 3.8 | 0.22 | 5.80 |

Findings
5. **DKT-simulated validity cannot distinguish selectors.** Flip-validity is 0.90–0.96 for
   every method including random (the base P(target) is already high at a random
   decision point), and appending five correct answers moves P(target) to 0.81–0.82
   regardless of *which* five. This is Study 1's calibration result seen from the other
   side: the DKT cannot score a study guide.
6. **Set-level verification from the log is not possible on XES3G5M.** Only 0–1% of
   recommended re-attempts were actually taken by the student in the next 30
   interactions, for every selector. There is no realized-outcome comparison to make.
   The honest set-level evidence is model-based (tau_T, tau_DR) plus evaluability.
7. **Ranking by tau_DR alone selects off-support.** It picks candidates with mean
   propensity 0.02 (students like this one almost never did this), evaluability 27%,
   and the longest gaps. Its heavy-tailed point estimates (§3.3) are largest exactly
   where the data are thinnest. This is the failure mode the LCB and support filter exist
   for: the full method restores evaluability to 100% and mean propensity to 0.14, at a
   cost of tau_T 0.043 → 0.021.
8. **Candidate pools are off-distribution by construction.** Observed re-attempts have
   median gap 10^4.0 s (~3 h, 90th pct ~1 week); candidate pools average 10^5.8 s (~7 days)
   because the pool is "last 60 positions". A recommender proposing week-old items is
   proposing something the log rarely shows. This is a property of the problem, not a bug,
   and argues for a recency-bounded pool.

## 5. Design-choice ablation (one change at a time)

| Change | Where measured | Effect |
|---|---|---|
| Objective: predicted correctness → causal lift | §3, corrections top-20% | −0.081 → +0.061 (sign flip); reviews −0.010 → +0.050 |
| Debiasing: T-learner → DR-learner | §3 Qini | corr 126 → 277; rev 220 → 286; IPW top-20% corr +0.025 → +0.099 |
| Meta-learner: X-learner | §3 | worst of the three on both arms; not recommended here |
| Pessimism: tau_T → tau_T − 1·sd | §3 / §4 | ranking quality drops slightly (Qini 126 → 112, 220 → 161) but set-level tau_T unchanged (0.043 → 0.041) and corrections share preserved; cheap insurance |
| One per area | §4 | tau_T 0.041 → 0.027, same-area share 0.21 → 0.16; trades lift for coverage, as intended |
| Support filter (e ≥ 0.02) | §4 | evaluability 0.69 → 1.00, mean e 0.10 → 0.14, tau_T 0.041 → 0.021; removes the off-support picks tau_DR is drawn to |
| Selecting on tau_DR instead of LCB | §4 | evaluability 0.69 → 0.27, e 0.10 → 0.02: good ranker, unsafe selector |
| Window N = 5, area level 2 | fixed | not ablated in this run (`--window`, `--area_level` flags) |

## 6. What this supports, and what it does not

Supported, offline, against the published baseline on its own benchmark:
- Ranking past questions by estimated causal lift identifies re-attempts that beat
  moving on (+6 to +10 points on corrections, +5 to +7 on reviews, top 20%), where the
  DKT predicted-correctness signal used by KTCF identifies re-attempts that are worse
  than moving on or no better than random.
- Propensity-debiased learners rank better than the naive effect model, and the naive
  effect model's signal on corrections is substantially selection.
- The DKT's own validity score is uninformative about which guide is better (0.90–0.96
  for everything), so KTCF's headline metric cannot adjudicate between methods.

Not supported, and should be stated as limitations:
- No claim that a recommended guide raises scores: realized re-attempts are ~0.5% of
  recommendations, so no observed-outcome set-level comparison exists on XES3G5M.
- tau_DR magnitudes are not usable as effect sizes; they rank well and extrapolate badly.
- The candidate pool and the logged re-attempts live at different gaps; support-aware
  selection is necessary, not optional.
- Single dataset, 300-student set-level sample, one seed, N = 5 window, level-2 areas.

## 7. Next steps, in order of value per hour
1. Recency-bounded candidate pool (e.g. ≤ 1 week) and rerun §4; expect evaluability up and
   the tau_DR pathology to shrink.
2. ASSISTments 2012/2017 as the second dataset: higher re-attempt rate makes the realized-
   outcome check in §4 feasible, and the covariates are already dataset-agnostic.
3. Seeds × 3, window N ∈ {3, 5, 10}, area level ∈ {1, 2, 3}; cluster-bootstrap CIs on the
   §3 table (the metrics module is ready; wrap `qini_coefficient` in a student resample).
4. Replace the one-flip KTCF proxy with the real gradient search from `ktcf-work` if a
   GPU box is available; the one-flip form is its first-order approximation.

# Study 2 — Uplift-objective recourse for knowledge tracing: results

Document of record for Study 2. Every number here comes from a file under `out/uplift/` (cited next to each table). All runs: 3 seeds (0/1/2), 20 student-bootstrap refits, training on train-split learners only, evaluation on held-out learners.

## 1. Question

> For a student at a given moment, which past questions, if re-attempted now, would most improve
> their subsequent performance compared with attempting a new question in the same area — and can
> that be verified from what logged students actually did afterwards?

This replaces KTCF's objective ("which past wrong answers, if flipped, make the student model
predict the target correct"). Three changes: reviews of previously correct items are eligible
alongside corrections; time since last attempt is part of the estimate; the recommendation is
scored against observed outcomes rather than the student model's own prediction.

## 2. Data

| | XES3G5M | Duolingo SLAM (en_es) | ASSISTments 2012-13 |
|---|---|---|---|
| Unit | question attempt | token in exercise | skill-tagged original problem |
| Interactions (clean) | 5,491,578 | 3,396,935 | 2,533,720 |
| Students (clean) | 18,064 | 2,593 | 18,180 |
| Held-out split | by student: 14,452 train / 3,612 test | by time within learner (shared-task split; all 2,593 on both sides) | by student hash: 14,572 / 3,608 |
| "Area" | level-2 KC (53) | POS tag (16) | skill_id (265) |
| Re-attempts of same item | 183,806 (3.35%) | 2,490,031 (73.3%) | 124,838 (4.9%) |
| of which corrections / reviews | 47,175 / 136,631 | 290,938 / 2,199,093 | 43,908 / 80,930 |
| Student model (test AUC) | KTCF released DKT, 0.777 | GBM history model, 0.799 | GBM history model, 0.754 |

Sources: `out/uplift/*/s1_log.json`, `s2.log`. "Held out" means unseen students on XES3G5M and ASSISTments, and each learner's later exercises on SLAM; in all three the model never sees the outcomes it is scored on. ASSISTments is the common benchmark of DKT-Forget, DAS3H, HawkesKT and LPKT; the GBM student model's AUC is in line with DKT-Forget's published 0.73 on this data.

Action labels: `new` (first attempt), `correction` (re-attempt after a wrong answer), `review` (re-attempt after a right answer). Outcomes: **area** = accuracy on the next 5 same-area items in later exercises, excluding the item itself; **item** = correct at the item's next encounter; **area20** = next 20 same-area items.

## 3. Average effects are mostly selection

Naive effect of a re-attempt vs a new item in the same area (area outcome, train folds) and the doubly-robust estimate after propensity adjustment:

| | corrections naive → DR | reviews naive → DR |
|---|---|---|
| XES3G5M | −0.074 → −0.015 | +0.031 → −0.013 |
| SLAM | −0.046 → +0.007 | +0.018 → +0.009 |
| ASSISTments | −0.067 → +0.015 | +0.043 → −0.027 |

Students who redo mistakes are weaker, students who redo successes are stronger; most of the raw "effect" of each action is who does it. After adjustment both averages are within ±0.03 of zero on every dataset. Any value is in heterogeneity, which §4 tests. Source: `s3*.log`.

## 4. Headline: ranking reviews by causal lift

For every held-out review (treated) and matched new-item event in the same area (control), each ranker scores the event; we take the top 20% of the ranking and report observed outcome among treated minus observed outcome among controls in that slice. τ_LCB = T-learner lift minus one bootstrap sd (the reported estimator; §7). Mean over 3 seeds, sd in parentheses for τ_LCB; predicted-correctness (`p_dkt`, the student model's P(correct), KTCF's signal) and random have no seed dependence.

| Outcome | | XES3G5M | SLAM | ASSISTments |
|---|---|---|---|---|
| Area, all | τ_LCB | **0.080** (.013) | **0.175** (.003) | **0.144** (.011) |
| | predicted correctness | −0.010 | 0.047 | 0.030 |
| | random | 0.022 | 0.047 | 0.056 |
| Area, headroom < 0.8 | τ_LCB | **0.111** (.004) | **0.135** (.011) | **0.077** (.024) |
| | predicted correctness | −0.040 | 0.028 | −0.019 |
| | random | 0.012 | 0.020 | 0.036 |
| Item, all | τ_LCB | **0.184** (.019) | **0.321** (.013) | **0.301** (.002) |
| | predicted correctness | 0.028 | 0.073 | 0.006 |
| | random | 0.054 | 0.069 | 0.102 |
| Item, headroom < 0.8 | τ_LCB | **0.229** (.024) | **0.269** (.010) | **0.211** (.015) |
| | predicted correctness | 0.020 | 0.086 | 0.013 |
| | random | 0.051 | 0.060 | 0.052 |

Lift-ranked reviews beat predicted-correctness-ranked reviews in all 12 cells; predicted correctness is at or below random in 11 of 12. "Headroom" restricts to decision points where the student's recent same-area accuracy is below 0.8. Held-out counts (reviews / controls): XES3G5M 16,624 / 82,637 (area), 701 / 3,459 (item; underpowered, reported for direction only); SLAM 380,564 / 128,877 and 347,383 / 46,467 (corrections 42,922 / 46,045); ASSISTments 9,300 / 45,789 and 1,755 / 7,759. Source: `out/uplift/headline_table.csv`; per-seed files `*/s5_event_qini*_s*.csv`.

Calibration: by decile of predicted lift, observed treated-minus-control gain rises monotonically on all three datasets (e.g. SLAM reviews, area: +0.007 lowest decile → +0.18 top decile). Source: `*/s5_tau_calibration*_s0.csv`.

**Uncertainty on the gap.** Student-clustered bootstrap (300 resamples per seed, mean of 3 seeds) for the difference in top-20% gain, lift (τ_LCB) minus predicted correctness, and lift minus random, on the same held-out events:

| Reviews | Area: vs pred. corr. [95% CI] | vs random | Item: vs pred. corr. | vs random |
|---|---|---|---|---|
| XES3G5M | +0.090 [+0.081, +0.100] | +0.060 [+0.049, +0.070] | +0.156 [+0.093, +0.214] | +0.143 [+0.068, +0.206] |
| SLAM | +0.128 [+0.119, +0.139] | +0.129 [+0.121, +0.139] | +0.248 [+0.225, +0.268] | +0.247 [+0.228, +0.268] |
| ASSISTments | +0.114 [+0.091, +0.133] | +0.080 [+0.061, +0.096] | +0.295 [+0.242, +0.346] | +0.233 [+0.172, +0.288] |

All twelve intervals exclude zero. Source: `out/uplift/paired_table.csv`.

## 5. Corrections: platform-dependent

| Outcome | | XES3G5M | SLAM | ASSISTments |
|---|---|---|---|---|
| Area, all | τ_LCB / pred. corr. / random | 0.019 / −0.081 / −0.097 | 0.079 / −0.004 / −0.019 | −0.033 / 0.032 / −0.029 |
| Item, all | τ_LCB / pred. corr. / random | 0.063 / 0.001 / 0.009 | 0.100 / −0.015 / −0.074 | 0.028 / −0.161 / −0.063 |

Positive on XES3G5M and SLAM, null on ASSISTments at the area level, where a same-problem correction is almost always an immediate retry after a miss. Corrections help where a correction is a return to the item, not an instant retry.

Clustered CIs on the gap vs predicted correctness: XES3G5M area +0.099 [+0.071, +0.133], item +0.062 [−0.053, +0.177] (n = 306, inconclusive); SLAM area +0.083 [+0.067, +0.095], item +0.116 [+0.098, +0.135]; ASSISTments area **−0.065 [−0.103, −0.021]** (lift ranking is worse than the heuristic and no better than random, −0.004 [−0.031, +0.020]), item +0.190 [+0.016, +0.333] (n = 936). The ASSISTments area cell is the one place in the study where lift ranking loses; it is the case where a correction is an instant retry, and the veto below, not the ranker, is the right tool.

**New-practice policy** (re-attempt only if τ_LCB > 0, otherwise a new item in the same area;
area outcome, IPW-weighted on held-out events):

| | share of corrections sent to new practice | those re-attempts vs new item | policy gain |
|---|---|---|---|
| XES3G5M | 75% | −0.060 | **+0.050** |
| SLAM | 62% | −0.018 | **+0.012** |
| ASSISTments | 73% | −0.009 | **+0.006** |

For reviews the same policy is neutral or slightly harmful (−0.006 / +0.002 / −0.017): reviews beat new practice on average everywhere, so the model's job there is to rank, not to veto. Deployed rule: apply the veto to corrections only. Source: `*/s7_new_practice_s0.csv`.

**Joint model (ablation, rejected).** One effect model over both re-attempt types with action type as
a feature, so corrections and reviews are scored on one scale. τ_LCB top-20% gain, joint vs separate-arm
models (mean over 3 seeds): reviews area XES3G5M 0.043 vs 0.080, SLAM 0.181 vs 0.175, ASSISTments 0.152
vs 0.144; reviews item SLAM 0.282 vs 0.321, ASSISTments 0.169 vs 0.301; corrections worse everywhere
(e.g. XES3G5M −0.046 vs 0.019, SLAM item 0.042 vs 0.100). Pooling the arms costs up to 13 points on
item-level reviews; the separate-arm models are retained. When both arms compete in one ranking, reviews
fill 89–98% of the top slice, so the practical recommender is "rank reviews; handle corrections by the
veto." Source: `out/uplift/*/s12_joint*_s*.csv`.

**Veto threshold.** A threshold t* learned on train (maximising IPW policy value) versus the fixed
τ_LCB ≤ 0 rule, policy gain over always-re-attempt (3-seed means): reviews XES3G5M −0.004 → +0.014,
SLAM area +0.006 → +0.011, SLAM item −0.012 → +0.009, ASSISTments −0.015 → −0.002 and −0.046 →
−0.027; corrections XES3G5M 0.049 → 0.045, SLAM item 0.006 → 0.027, ASSISTments item 0.063 → 0.024.
The learned threshold is negative (−0.01 to −0.05: "re-attempt unless the model is fairly sure it
hurts"); it removes the fixed rule's harm on reviews and overfits on the small ASSISTments correction
set. Deployed rule: learned threshold for reviews, fixed τ_LCB ≤ 0 for corrections.

## 6. Secondary results

**20-item window.** Reviews τ_LCB vs predicted correctness vs random: XES3G5M 0.039 / −0.001 / 0.028 (effect washes out); SLAM 0.165 / 0.059 / 0.042 and ASSISTments 0.158 / 0.011 / 0.061 (effect persists). Short-range on math platform practice, longer-range on language and skill-builder data. Source: `headline_table.csv`, outcome `_area20`.

**Timing.** Not evaluable. The estimated lift curve over gap is flat on SLAM (≤1 point between the
actual and model-optimal gap) and dominated by within-session re-attempts on ASSISTments; observed
gain shows no gradient with distance from the model-optimal gap (SLAM +0.018 / +0.026 / +0.016 /
+0.020 across distance bins; ASSISTments +0.014 / +0.033 / +0.015 / +0.038). Fewer than 0.3% of
logged reviews occur at HLR-predicted recall below 0.5, so the "review when about to forget" rule has
no observed support. Source: `*/s6_timing_review_by_*.csv`.

**Set level (k = 5 study lists).** Not established. On XES3G5M and ASSISTments 0.5% and 2–4% of
recommended items were ever re-attempted by the student, so no observed-outcome comparison exists.
On SLAM (38% realized) the per-area-baseline gain of lift-ranked lists over the learner's own
trajectory was +0.029 [+0.017, +0.039] on all tokens and −0.001 [−0.022, +0.020] on content words:
the all-token gain is carried by function-word reviews. The student model's own simulated validity is
0.90–0.97 for every selector including random and cannot adjudicate. Source: `*/s4_set_summary*.csv`.

## 6b. Transfer across platforms

The covariates carry no item or skill identity, so a model fitted on one platform can score another with no retraining. Reviews, top-20% gain, mean ± sd over 3 seeds:

| evaluated on | in-domain τ_LCB | zero-shot τ_LCB (model from the other platform) | predicted correctness | random |
|---|---|---|---|---|
| ASSISTments, item | 0.301 | **0.117** ± .015 (from SLAM) | 0.006 | 0.062 |
| SLAM, item | 0.321 | **0.190** ± .058 (from ASSISTments) | 0.073 | 0.080 |
| ASSISTments, area | 0.144 | 0.065 ± .014 (from SLAM) | 0.030 | 0.057 |
| SLAM, area | 0.175 | 0.044 ± .007 (from ASSISTments) | 0.047 | 0.047 |

At the item level a model trained on Spanish speakers learning English words recovers a quarter to a half of the in-domain lift on US middle-school math (and vice versa) and beats predicted correctness in both directions; at the area level there is no transfer, and corrections do not transfer at all. What makes a review worth doing *for the item itself* — recent accuracy, exposure count, gap, difficulty — is partly platform-independent; what makes it worth doing for the surrounding topic is not. Source: `out/uplift/transfer_table.csv`.

## 6c. Student-model ablation (pyKT DKT and DKT-Forget)

On SLAM and ASSISTments the student model of record is a gradient-boosted history model (GBM). To test
whether a sequence model changes anything, pyKT `dkt` and `dkt_forget` were trained on the same event
tables (concept = area, question = item; `s13_pykt_export.py`, `s14_pykt_predict.py`) and their
predictions substituted for `p_dkt`, then stages 3 and 5 rerun (seed 0). Test AUC on the evaluation
rows: SLAM GBM 0.799, DKT 0.750, DKT-Forget 0.741; ASSISTments GBM 0.754, DKT 0.729, DKT-Forget 0.731
(DKT-Forget's published ASSIST2012 AUC is ≈ 0.73).

Reviews, top-20% gain, τ_LCB / predicted correctness / random:

| | student model | area | item |
|---|---|---|---|
| SLAM | GBM (record, 3 seeds) | 0.175 / 0.047 / 0.047 | 0.321 / 0.073 / 0.069 |
| | DKT | 0.126 / 0.007 / 0.049 | 0.249 / 0.054 / 0.076 |
| | DKT-Forget | 0.123 / 0.008 / 0.049 | 0.272 / 0.053 / 0.076 |
| ASSISTments | GBM (record, 3 seeds) | 0.144 / 0.030 / 0.056 | 0.301 / 0.006 / 0.102 |
| | DKT | 0.110 / 0.028 / 0.056 | 0.277 / 0.049 / 0.102 |
| | DKT-Forget | 0.122 / 0.030 / 0.056 | 0.253 / 0.040 / 0.102 |

1. A real DKT does not rescue predicted-correctness ranking: 0.007–0.054 against random 0.049–0.102
   on every cell.
2. Lift ranking holds with the DKT at 3–7 points lower magnitude; the gap over predicted correctness
   stays at 8–23 points. The GBM is the better covariate because it sees item-level exposure and gap,
   which a concept-sequence DKT does not; it is reported as the student model of record on these two
   datasets, not as a stand-in.
3. Forgetting-aware vs plain DKT: no consistent difference (−0.024 to +0.023). The time information
   the ranker needs is already carried by `gap_log` and `p_hlr` as direct covariates.

Caveat: the SLAM DKT-Forget was trained on gap features pyKT discretised from timestamps exported in
seconds and divided as milliseconds, collapsing most gaps into 1–2 bins (`num_rgap = 7`); its lower AUC
reflects that, not the architecture. ASSISTments (`num_rgap = 19`) is the clean DKT vs DKT-Forget
comparison. One seed. Source: `out/uplift/{slam,assist}_{dkt,forget}/s5_event_qini*_s0.csv`.

## 7. Estimators

T-learner (two gradient-boosted outcome models), X-learner, DR-learner (doubly-robust
pseudo-outcome regression with cross-fitted propensity), all cross-fitted by student; τ_LCB =
T-learner lift minus one sd over 20 student-bootstrap refits. τ_LCB is reported because it is the
stable estimator (seed sd ≤ 0.024 in every review cell); τ_DR ranks as well or better on Qini but its
magnitudes are heavy-tailed (seed sd up to 0.079; 1st/99th percentile −0.64 / +1.16 on observed
events) and it is used only to confirm that debiasing does not reverse the ranking (it does not; on
XES3G5M corrections it strengthens it: IPW top-20% +0.047 vs T-learner +0.024). X-learner is worst of
the three everywhere.

## 8. What was retracted during the study

- 2026-11-06: a SLAM set-level gain of +0.06 was withdrawn. The metric compared a pick's next-5
  accuracy in the pick's own area with the learner's baseline in the target area; function-word areas
  run at ~97% and content-word areas at ~84%, so the gain measured area difficulty. Fixed to a
  per-area baseline; the corrected number is in §6.
- 2026-11-06: the content-word-only ablation showed every selector at zero, confirming the remaining
  +0.03 all-token gain was carried by function-word reviews.
- The DR-learner's review-arm top-20% gain did not reproduce across machines on XES3G5M (+0.050 vs
  +0.018); this is the instability in §7 and the reason τ_LCB is the reported estimator.

## 9. Claims and limitations

Claimed: (i) most of the observational effect of re-attempting is selection; (ii) ranking reviews by
estimated causal lift identifies re-attempts followed by 8–18 points higher same-area accuracy and
18–32 points higher item recall than ranking by predicted correctness, on three platforms, with
predicted correctness no better than random; (iii) the model also identifies corrections that should
be replaced by new practice; (iv) the student model's self-scored validity cannot distinguish
recommendation methods.

Not claimed: that delivering a study list to a student improves their performance. All evidence is observational and event-level: the re-attempts the method ranks highest were followed by larger gains when students happened to do them. Re-attempts were chosen by students and platform schedulers, not by the method; propensity weighting is applied throughout. A randomized study is the only test of the delivered recommendation. Other limits: on SLAM and ASSISTments the student model of record is a gradient-boosted history model, with pyKT DKT / DKT-Forget run as a one-seed ablation (§6c); the KTCF-flip baseline on those datasets is a one-flip approximation; item-level outcomes on XES3G5M are underpowered.
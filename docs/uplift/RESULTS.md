# Study 2 — Uplift-objective recourse for knowledge tracing: results

Document of record for Study 2. Every number here comes from a file under `out/` (cited next to each table). All runs: 3 seeds (0/1/2), 20 student-bootstrap refits, training on train-split learners only, evaluation on held-out learners.

## 1. Question

> For a student at a given moment, which past questions, if re-attempted now, would most improve their subsequent performance compared with attempting a new question in the same area — and can that be verified from what logged students actually did afterwards?

This replaces KTCF's objective ("which past wrong answers, if flipped, make the student model predict the target correct"). Three changes: reviews of previously correct items are eligible alongside corrections; time since last attempt is part of the estimate; the recommendation is scored against observed outcomes rather than the student model's own prediction.

## 2. Data

| | XES3G5M | Duolingo SLAM (en_es) | ASSISTments 2012-13 |
|---|---|---|---|
| Unit | question attempt | token in exercise | skill-tagged original problem |
| Interactions (clean) | 5,491,578 | 3,396,935 | 2,533,720 |
| Students | 18,064 | 2,593 | 18,180 |
| "Area" | level-2 KC (53) | POS tag (16) | skill_id (265) |
| Re-attempts of same item | 183,806 (3.35%) | 2,490,031 (73.3%) | 124,838 (4.9%) |
| of which corrections / reviews | 47,175 / 136,631 | 290,938 / 2,199,093 | 43,908 / 80,930 |
| Student model (test AUC) | KTCF released DKT, 0.777 | GBM history model, 0.799 | GBM history model, 0.754 |

Sources: `out/*/s1_log.json`, `s2.log`. ASSISTments is the common benchmark of DKT-Forget, DAS3H, HawkesKT and LPKT; the GBM student model's AUC is in line with DKT-Forget's published 0.73 on this data.

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

Lift-ranked reviews beat predicted-correctness-ranked reviews in all 12 cells; predicted correctness is at or below random in 11 of 12. "Headroom" restricts to decision points where the student's recent same-area accuracy is below 0.8. Held-out counts (reviews / controls): XES3G5M 16,624 / 82,637 (area), 701 / 3,459 (item; underpowered, reported for direction only); SLAM 380,564 / 128,877 and 347,383 / 46,467; ASSISTments 9,300 / 45,789 and 1,755 / 7,759. Source: `out/headline_table.csv`; per-seed files `*/s5_event_qini*_s*.csv`.

Calibration: by decile of predicted lift, observed treated-minus-control gain rises monotonically on all three datasets (e.g. SLAM reviews, area: +0.007 lowest decile → +0.18 top decile). Source: `*/s5_tau_calibration*_s0.csv`.

## 5. Corrections: platform-dependent

| Outcome | | XES3G5M | SLAM | ASSISTments |
|---|---|---|---|---|
| Area, all | τ_LCB / pred. corr. / random | 0.019 / −0.081 / −0.097 | 0.079 / −0.004 / −0.019 | −0.033 / 0.032 / −0.029 |
| Item, all | τ_LCB / pred. corr. / random | 0.063 / 0.001 / 0.009 | 0.100 / −0.015 / −0.074 | 0.028 / −0.161 / −0.063 |

Positive on XES3G5M and SLAM, null on ASSISTments at the area level, where a same-problem correction is almost always an immediate retry after a miss. Corrections help where a correction is a return to the item, not an instant retry.

**New-practice policy** (re-attempt only if τ_LCB > 0, otherwise a new item in the same area; area outcome, IPW-weighted on held-out events):

| | share of corrections sent to new practice | those re-attempts vs new item | policy gain |
|---|---|---|---|
| XES3G5M | 75% | −0.060 | **+0.050** |
| SLAM | 62% | −0.018 | **+0.012** |
| ASSISTments | 73% | −0.009 | **+0.006** |

For reviews the same policy is neutral or slightly harmful (−0.006 / +0.002 / −0.017): reviews beat new practice on average everywhere, so the model's job there is to rank, not to veto. Deployed rule: apply the veto to corrections only. Source: `*/s7_new_practice_s0.csv`.

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

Claimed: (i) most of the observational effect of re-attempting is selection; (ii) ranking reviews by estimated causal lift identifies re-attempts followed by 8–18 points higher same-area accuracy and 18–32 points higher item recall than ranking by predicted correctness, on three platforms, with predicted correctness no better than random; (iii) the model also identifies corrections that should be replaced by new practice; (iv) the student model's self-scored validity cannot distinguish recommendation methods.

Not claimed: that delivering a study list to a student improves their performance. All evidence is observational and event-level: the re-attempts the method ranks highest were followed by larger gains when students happened to do them. Re-attempts were chosen by students and platform schedulers, not by the method; propensity weighting is applied throughout. A randomized study is the only test of the delivered recommendation. Other limits: SLAM and ASSISTments use a gradient-boosted history model rather than a DKT (pyKT DKT swap is a planned ablation); the KTCF-flip baseline on those datasets is a one-flip approximation; item-level outcomes on XES3G5M are underpowered.
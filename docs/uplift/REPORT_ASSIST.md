# Third dataset: ASSISTments 2012-13 (skill-tagged original problems)

Pipeline identical to SLAM (loader `s1_events_assist.py`; student model = gradient-boosted history model, test AUROC 0.754 — DKT-Forget's published ASSIST2012 AUC is ~0.73; HLR theta reused from Duolingo as the spaced-repetition baseline). question = problem_id, area = skill_id (265 skills), response = 1[correct == 1], split 80/20 by student.

## Data
2,533,720 problems, 18,180 students. Re-attempts of the SAME problem: 4.9% (80,930 reviews, 43,908 corrections). Skill builders assign a different problem on the same skill, so same-problem repeats are rare (like XES3G5M), while same-skill practice is dense. 63% of rows are in Mastery (skill-builder) problem sets.

## Average effects (train folds)
| arm | naive ATE (area) | DR ATE (area) | naive (item) | DR (item) |
|---|---|---|---|---|
| correction | -0.067 | +0.015 | -0.128 | -0.126 |
| review | +0.043 | -0.027 | +0.079 | -0.057 |
Selection pattern replicates for the third time: corrections look harmful and reviews helpful until
debiased, after which both averages are near zero.

## Ranking (held-out, observed gain in top 20%, treated minus control)
Area outcome (next-5 same-skill):
| ranker | corrections (n=5,210) | reviews (n=9,300) |
|---|---|---|
| random | -0.029 | +0.056 |
| predicted correctness | +0.032 | +0.030 |
| tau_T | -0.020 | **+0.160** (IPW +0.089) |
| tau_DR | -0.024 | +0.122 |
| tau_LCB | -0.024 | +0.142 |
Headroom (pre_area < 0.8): reviews tau_LCB +0.118 vs predicted correctness -0.020 vs random +0.036; corrections null.
Item outcome (same problem right next time; n = 936 corrections / 1,755 reviews):
| ranker | corrections | reviews |
|---|---|---|
| random | -0.063 | +0.102 |
| predicted correctness | -0.161 | +0.006 |
| tau_T | +0.022 | +0.289 |
| tau_DR | -0.065 | **+0.311** (IPW +0.245) |

## Timing (reviews, area model): gain +0.012 within 0.5 log10-s of model-optimal gap, ~0 beyond. Weak; not actionable.
## New practice policy (area): corrections +0.011 (policy sends 70% to a new problem); reviews -0.015 (LCB too conservative here: reviews beat new even where tau_LCB <= 0).
## Set level: not evaluable. Only 84 of 600 sampled students have a long enough test tail, realized share 2-4%, n_realized 6-12 per selector. Same wall as XES3G5M.

## What ASSISTments settles across the three datasets
1. REVIEWS, ranked by causal lift, are followed by gains the predicted-correctness ranking does not find:
   area outcome +0.16 vs +0.03 (ASSIST), +0.17 vs +0.05 (SLAM), +0.07 vs -0.01 (XES3G5M);
   item outcome +0.31 vs +0.01 (ASSIST), +0.29 vs +0.07 (SLAM). Three datasets, two outcomes, same direction.
2. CORRECTIONS are the unstable arm: positive on XES3G5M and SLAM, null on ASSISTments at the area level.
   On ASSISTments a same-problem correction is usually an immediate retry (median gap short), so there
   is little to learn from it; the new-practice policy (+0.011) is the right response and it replicates.
3. The selection story (naive effect = who re-attempts) replicates on all three.
4. Set-level benefit is evaluable only where same-item repeats are dense (SLAM) and there it is null on
   content words. ASSISTments and XES3G5M cannot test it. The randomized study remains the only route.

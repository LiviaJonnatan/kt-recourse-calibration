# Second dataset: Duolingo SLAM (en_es) — full run, 2026-11-05

Same five stages as the XES3G5M run, with a SLAM loader (`s1_events_slam.py`), a
gradient-boosted history model as the student model (`s2_student_slam.py`, 0.799 AUROC held
out; the shared task's logistic baseline was 0.774), half-life regression fitted on the
Duolingo 13M traces (`s0_hlr.py`, MAE 0.140 vs 0.173 constant) as the spaced-repetition
baseline and as a treated-arm covariate, and `s4_select_slam.py` for sets + case studies.

Mapping: question = surface token; area = POS (16); re-attempt = next encounter with the
token; outcome = accuracy on the next 5 same-POS tokens in later exercises.

## Data
3,396,935 tokens, 2,593 learners, 309,075 exercises. 73.3% of events are re-attempts
(2,199,093 reviews, 290,938 corrections) vs 3.35% on XES3G5M. 3.09M events with a full window.

## Average effects (train folds)
| arm | naive ATE | DR ATE |
|---|---|---|
| correction | −0.046 | +0.007 |
| review | +0.019 | +0.007 |
Same selection pattern as XES3G5M; after debiasing both are slightly positive.

## Ranking signal (held-out events, observed gain in top 20%)
| ranker | corrections | reviews |
|---|---|---|
| random | −0.019 | +0.047 |
| predicted correctness (p_dkt) | −0.004 | +0.047 |
| predicted success after action (mu1) | +0.033 | +0.042 |
| easiest first | −0.027 | +0.044 |
| tau_T | +0.073 | +0.167 |
| tau_X | +0.019 | +0.072 |
| tau_DR | +0.063 | +0.162 |
| **tau_LCB** | **+0.074** | **+0.174** |
Qini (corr / rev): random 5 / −84; p_dkt 367 / −406; tau_T 899 / 7960; tau_DR 1244 / 7994; tau_LCB 989 / 7536.
Four groups among logged re-attempts: corrections 10% persuadable, 45% sure things; reviews 4% persuadable, 77% sure things.

## Chosen sets: 393 learners, k = 5, recency-bounded pool (last 200 tokens), realized within next 100 tokens
| selector | realized share | n with outcome | realized y | y anyway | realized gain [95% CI] | corr / rev | mean e |
|---|---|---|---|---|---|---|---|
| random | 18% | 213 | 0.868 | 0.833 | +0.049 [+0.015, +0.079] | 0.7 / 4.3 | 0.48 |
| predicted correctness | 29% | 262 | 0.890 | 0.833 | +0.047 [+0.020, +0.072] | 0.0 / 5.0 | 0.61 |
| KTCF-flip (corrections only) | 15% | 152 | 0.843 | 0.832 | +0.048 [+0.005, +0.090] | 4.9 / 0 | 0.52 |
| HLR lowest recall | 4% | 51 | 0.846 | 0.833 | +0.019 [−0.058, +0.089] | 2.1 / 2.9 | 0.35 |
| raw gain (tau_T) | 31% | 272 | 0.897 | 0.833 | +0.066 [+0.037, +0.093] | 0.7 / 4.3 | 0.60 |
| uplift_dr | 15% | 177 | 0.903 | 0.833 | +0.062 [+0.034, +0.090] | 0.3 / 4.7 | 0.38 |
| uplift_lcb | 34% | 291 | 0.901 | 0.833 | +0.073 [+0.046, +0.098] | 0.6 / 4.4 | 0.62 |
| + one per area | 37% | 336 | 0.906 | 0.833 | +0.073 [+0.049, +0.096] | 0.7 / 4.3 | 0.67 |
| **+ support filter (full)** | **37%** | 336 | 0.906 | 0.833 | **+0.073 [+0.050, +0.098]** | 0.7 / 4.3 | 0.67 |

Paired on learners with an outcome under both selectors (uplift_full minus baseline, 2000 bootstrap):
| vs | n | diff [95% CI] |
|---|---|---|
| random | 164 | +0.041 [+0.012, +0.066] |
| predicted correctness | 200 | +0.016 [−0.005, +0.037] |
| KTCF-flip | 116 | +0.054 [+0.019, +0.087] |
| raw gain | 226 | +0.010 [+0.001, +0.020] |
| HLR lowest recall | 40 | +0.035 [−0.023, +0.090] |

## What this adds to the XES3G5M result
1. The ranking result replicates and strengthens: lift-ranked reviews are followed by gains
   3–4× larger than correctness-ranked reviews; corrections flip sign. Both datasets, same direction.
2. First observed-outcome set comparison. Our picks are re-encountered twice as often as random
   (37% vs 18%) and, when they are, followed by +7.3 points over what the learner did anyway;
   paired against KTCF's objective +5.4 [+1.9, +8.7], against random +4.1 [+1.2, +6.6].
3. Against predicted-correctness the paired set-level gap is +1.6 [−0.5, +3.7]: positive, not
   significant at this sample. The event-level gap is large; the set-level gap is small because
   both selectors end up picking frequently-recurring reviews (see 5).
4. Debiasing + LCB + area rule each add a little (+0.066 → +0.073) and raise realized share
   (31% → 37%); tau_DR alone again drifts off-support (e 0.38, realized 15%).
5. Caveat that matters: the method's picks skew to high-frequency function words ('a', 'you',
   'where', 'and'; mean e 0.67). Part of the realized gain is "items that recur anyway". A
   content-word-only pool (exclude DET/PRON/ADP/CONJ) is the next ablation; expect smaller
   realized share and a cleaner pedagogical reading.
6. Realized outcomes come from Duolingo's scheduler and the learner, not our recommender;
   the claim is "items we rank highest were followed by larger gains", with propensity
   weighting on, not "our picks caused them".

## Case studies
`out_slam/s4_cases.md`: three learners, last 8 exercises token-by-token, the decision point,
what happened over the next 5 same-POS tokens, and every selector's five picks with action,
exposure count, gap, tau_T, tau_DR, propensity, HLR recall, and whether the pick was realized.

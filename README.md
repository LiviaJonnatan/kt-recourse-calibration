# kt-recourse-calibration

## Study 1: Do knowledge tracing models know what interventions do?

### Motivation

Counterfactual recourse methods for knowledge tracing (KTCF, DSMOEA, RCKT, and related work) recommend interventions such as “re-attempt the questions you got wrong” or “review this concept.” They evaluate those recommendations by asking the same KT model whether the student’s predicted performance improves. This assumes the model can predict what a re-attempt or a review actually does to a student. That assumption has not been tested. If public KT datasets rarely contain re-attempts, the models were never trained on the events they are being asked to predict, and recourse validity scores may say little about students.

### Research questions

1. Prevalence. How often do students in public KT datasets re-attempt a question they previously answered, and how are those repeats distributed across time gaps, concepts, difficulty, and position in the sequence? We separate re-attempts after a wrong answer (correction) from re-doing a question already answered correctly (review).
2. Observed effects. When a re-attempt does occur, what happens? What is the observed probability of success on the re-attempt, how does retention on reviewed questions decay with time, and how does performance on related concepts change afterward, relative to matched students who did not re-attempt?
3. Model calibration. Do KT models of different families (concept-level without forgetting, question-aware, forgetting-aware) predict those observed effects? And when a counterfactual intervention is applied in the KTCF manner (flipping an earlier wrong answer to right), does the model’s predicted improvement on later performance match the observed change in students who really did correct that answer?

### Contribution

- The first measurement of re-attempt and review prevalence and observed effects across public KT datasets, released as reusable audit code.
- A calibration test for counterfactual recourse in KT: a method and results showing how far model-predicted intervention effects are from observed ones, broken out by intervention type, item difficulty, and model family.
- Where the data support it, a KT model trained with correction and review as explicit event types and with forgetting, evaluated on its ability to predict observed re-attempt outcomes.

### What this study does not claim

Observed effects are associations, not causal estimates: students who re-attempt differ from students who do not, and public logs contain no randomized interventions. The study tests whether model predictions and observed outcomes agree, not which interventions teachers should assign.

### Datasets

XES3G5M (primary: timestamps, knowledge-component hierarchy, question text), with ASSISTments and EdNet-KT1 as datasets where repeated attempts are a platform feature. Final dataset choice depends on the prevalence results of question 1.

### Status

Phase 0–3 (setup, KTCF reproduction, prevalence audit, observed effects) in progress. Calibration (Phase 4) follows once the audit identifies which datasets contain enough repeats.

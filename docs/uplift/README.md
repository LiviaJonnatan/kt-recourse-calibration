# src/uplift — how to run Study 2

Results and interpretation: `docs/uplift/RESULTS.md`. This file is the run book only.

## Files
| stage | script | reads | writes |
|---|---|---|---|
| 0 | `s0_hlr.py` | Duolingo HLR traces (csv or zip) | `hlr_theta.json` |
| 1 | `s1_events.py` / `s1_events_slam.py` / `s1_events_assist.py` | raw dataset | `events.parquet`, `s1_log.json` |
| 1b | `s1b_outcomes.py` | `events.parquet` | adds `y_item`, `lag_next`, `y_area20` |
| 2 | `s2_dkt.py` (XES3G5M, KTCF checkpoint) / `s2_student_slam.py` (SLAM, ASSISTments) | events | `p_dkt_{train,test}.parquet` |
| 3 | `s3_uplift.py` | events + p_dkt | `uplift_{arm}<tag>_s<seed>.pkl`, `scored_test_{arm}<tag>_s<seed>.parquet` |
| 5 | `s5_event_eval.py` | scored_test | `s5_event_qini<tag>_s<seed>[_hr0.8].csv`, calibration, curves |
| 4 | `s4_select.py` (XES3G5M) / `s4_select_slam.py` (SLAM, ASSISTments) | events, models | `s4_sets*.parquet`, `s4_set_summary*.csv`, `s4_cases*.md` |
| 6 | `s6_timing.py` | item-outcome models | `s6_timing_review_by_{dist,hlr}.csv` |
| 7 | `s7_new_practice.py` | scored_test | `s7_new_practice<tag>.csv` |
| 8 | `s8_aggregate.py` | all `s5_event_qini*` | `out/headline_table.csv` |
| — | `metrics.py` | | Qini, uplift@k, IPW weights, four-group, DR set value |

## Setup
```
uv add pandas numpy scikit-learn pyarrow tabulate
```
No PyTorch: `s2_dkt.py` reads KTCF's checkpoint zip directly and runs the LSTM in NumPy.

Data layout (nothing under `data/raw/` is committed; see `data/README.md`):
```
data/raw/XES3G5M/question_level/{train_valid_sequences_quelevel,test_quelevel}.csv
data/raw/XES3G5M/metadata/questions.json
data/raw/slam/en_es_slam_20190204.{train,dev,test}   + _{dev,test}.key
data/raw/slam/learning_traces.13m.csv
data/raw/assist/assist2012_slim_csv.gz
ktcf-work/saved_model/qid_model.ckpt
```

## Tag convention
Stage 3 writes files suffixed `<tag>_s<seed>` where `<tag>` is `""` (area outcome), `_item`, or
`_area20`. Every later stage takes `--tag` equal to that full suffix (e.g. `--tag _item_s1`).

## Per dataset (run from `src/uplift/`; `D` ∈ xes, slam, assist)
Stage 1–2 once:
```
# xes
python s1_events.py --raw ../../data/raw/XES3G5M --out ../../out/xes --window 5 --area_level 2
python s2_dkt.py --ckpt ../../ktcf-work/saved_model/qid_model.ckpt --events ../../out/xes/events.parquet --out ../../out/xes --split test
python s2_dkt.py --ckpt ../../ktcf-work/saved_model/qid_model.ckpt --events ../../out/xes/events.parquet --out ../../out/xes --split train
# slam
python s0_hlr.py --zip ../../data/raw/slam/learning_traces.13m.csv --out ../../out/slam
python s1_events_slam.py --raw ../../data/raw/slam --out ../../out/slam --window 5 --theta ../../out/slam/hlr_theta.json
python s2_student_slam.py --out ../../out/slam
# assist  (copy out/slam/hlr_theta.json into out/assist first)
python s1_events_assist.py --raw ../../data/raw/assist/assist2012_slim_csv.gz --out ../../out/assist --theta ../../out/assist/hlr_theta.json
python s2_student_slam.py --out ../../out/assist
# all three
python s1b_outcomes.py --out ../../out/D
```
Stage 3–7 per seed S (add `--extra p_hlr` to stage 3 for slam and assist; not for xes):
```
python s3_uplift.py --out ../../out/D --ctrl_cap 400000 --treat_cap 300000 --boot 20 --seed S
python s5_event_eval.py --out ../../out/D --tag _sS
python s5_event_eval.py --out ../../out/D --tag _sS --headroom 0.8
python s7_new_practice.py --out ../../out/D --tag _sS
python s3_uplift.py --out ../../out/D --ctrl_cap 400000 --treat_cap 300000 --boot 20 --seed S --outcome y_item --tag _item
python s5_event_eval.py --out ../../out/D --tag _item_sS
python s5_event_eval.py --out ../../out/D --tag _item_sS --headroom 0.8
python s3_uplift.py --out ../../out/D --ctrl_cap 400000 --treat_cap 300000 --boot 20 --seed S --outcome y_area20 --tag _area20
python s5_event_eval.py --out ../../out/D --tag _area20_sS
```
Seed 0 only, slam and assist: `python s6_timing.py --out ../../out/D --tag _item_s0 --arms review --n 25000`.
Set level (optional): `python s4_select.py ...` (xes) / `python s4_select_slam.py --out ../../out/D --n_students 1000 --k 5 [--content_only] [--outcome y_item --model_tag _item]`.
Aggregate: `python s8_aggregate.py --out ../../out` → `out/headline_table.csv`.

## Runtimes (laptop, 1 process)
Stage 1: 3–5 min. Stage 2 (xes train): 6 min. Stage 3: 20–40 min per fit (SLAM `_item` slowest).
Stage 5/6/7: 1–3 min. Full 3-seed run, three datasets: ~12–15 h.

## Invariants (if these don't match, stop)
xes `s1_log.json`: after_pre2019 = 5,491,578; review + correction = 183,806. xes DKT test AUC 0.7765.
slam `s1_log.json`: tokens = 3,396,935; repeat_share = 0.733. slam student AUC 0.7993.
assist `s1_log.json`: rows_clean = 2,533,720; repeat_share = 0.0493. assist student AUC 0.7540.

## Known behaviour
- `tau_dr` magnitudes vary by seed and by machine (heavy-tailed pseudo-outcome); `tau_lcb` is stable. Report `tau_lcb`.
- `neg_gap` and `neg_p_hlr` rows in `s5_event_qini*` have NaN top-20% (controls carry no gap); ignore them.
- `s6_timing.py` output names carry no tag; one file per dataset.
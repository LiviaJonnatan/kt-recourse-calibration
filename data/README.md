# Data

Nothing in this folder except this file is tracked by git. Datasets are downloaded by each person into the layout below. `data/raw/` is never modified after download; `data/processed/` is regenerable from `src/` and can be deleted at any time.

```
data/
  README.md                  ← this file (tracked)
  raw/                       ← downloaded archives, unpacked, read-only
    XES3G5M/
    assistments2009/
    assistments2012/
    ednet-kt1/
  processed/                 ← outputs of src/audit/*.py; safe to delete
```

After downloading, make raw data read-only: `chmod -R a-w data/raw/`

## Datasets

### XES3G5M (primary)

| | |
| --- | --- |
| Source | https://github.com/ai4ed/XES3G5M (download link in its README points to Google Drive) |
| Paper | Liu et al., *XES3G5M: A Knowledge Tracing Benchmark Dataset with Auxiliary Information*, NeurIPS 2023 Datasets & Benchmarks. https://proceedings.neurips.cc/paper_files/paper/2023/hash/67fc628f17c2ad53621fb961c6bafcaf-Abstract-Datasets_and_Benchmarks.html |
| Licence | MIT (per the repository). Downloading implies agreement. |
| Unpack to | `data/raw/XES3G5M/` so that `kc_level/`, `question_level/`, `metadata/` sit directly under it |
| Size | ~18k students, ~5.5M interactions, 7,652 questions, 865 KCs; third-grade mathematics, Chinese online platform |

**Files we use** (verified 2026-10-26 with `src/audit/explore_xes3g5m.py`)

- `question_level/train_valid_sequences_quelevel.csv` — 30,965 rows, 14,453 students, folds 0–4 (~6.2k rows each). Columns: `fold, uid, questions, concepts, responses, timestamps, selectmasks`. **Every row is exactly 200 long and padded**: 4,446,374 real interactions, 1,746,626 padded (`selectmasks = -1`; padded cells hold `-1` for question, response and timestamp). Almost every student has exactly 2 rows (200 + a padded remainder); 243 have 1, one has 5. Sequence columns are comma-joined strings; multi-KC questions use `_` inside `concepts`.
- `question_level/test_quelevel.csv` — 3,613 rows, one per student, `fold = -1`. **Six columns only: no `selectmasks`.** No padding and no truncation: sequence lengths run 201–749 (mean 305), i.e. these are full histories. 1,102,810 interactions. No `uid` appears in both train and test.
- `metadata/questions.json` — 7,652 questions. Fields: `content, kc_routes, answer, analysis, type, options`. `type` is a **Chinese string**, not 0/1: `填空` = fill-in-the-blank (6,142), `单选` = single-choice (1,510). `kc_routes` is a list; 5,543 questions have 1 route, 1,780 have 2, up to 8.
- `metadata/kc_routes_map.json` for KC id → name. An English translation ships with the KTCF repo (see below).
- 7,619 distinct questions in train, 7,052 in test, 7,652 in the union; 33 questions occur only in test.

**Things to know before using it**

- There is **no raw interaction table**. The release is already pyKT-preprocessed. The maintainers state the original table cannot be reconstructed. For train, full histories are recovered by filtering `selectmasks == 1` and concatenating a `uid`'s rows in timestamp order (`src/audit/reconstruct.py`); about 3% of repeat pairs cross a row boundary and are recovered by the concatenation. Test needs no reconstruction.
- **Always filter `selectmasks == 1` on train before counting anything.** Padded `-1` cells otherwise masquerade as a question id and inflate repeat counts enormously (an unfiltered run showed 1.77M spurious "reviews" of question `-1` and a 1969 timestamp).
- **Mask question resolved** (`src/audit/check_mask.py`, output in `docs/exploration/2026-10-26_xes3g5m_check_mask.txt`): all 1,746,626 `-1` cells are pure filler (`-1` in every field, contiguous tail ending at position 199); no real interactions are repeated as history; consecutive rows of a student do not overlap. Train reconstruction by `uid` is safe. After cleaning, train and test agree closely (repeat share 4.33% vs 4.39%, students with a repeat 90.1% vs 89.8%, correction success 63% vs 62%, before the dedup rule below), so both files are used for prevalence.
- **Train sequence lengths after reconstruction:** 200–913 interactions per student, median 286, mean 308. Two students have pre-2019 timestamps (`uid` 12573, 2018; `uid` 10631, 2001); both are excluded from the audit.
- The KC-level files (`kc_level/`) expand one question into several rows and carry an `is_repeat` column that marks **KC continuation, not student re-attempts**. We do not use the KC-level files.
- **Timestamps are batch-level, not per-answer.** They are milliseconds, monotonic within a student, but about half of consecutive interactions share the exact same timestamp: a batch of questions started together gets one stamp. Per-question response time does not exist. Gaps between batches are typically ~20 minutes to days.
- **Same-batch duplicates are a logging artifact, not re-attempts** (`src/audit/inspect_same_batch.py`, output in `docs/exploration/2026-10-26_xes3g5m_same_batch.txt`). 45,472 train "repeats" fall inside one batch; 98.5% carry the identical answer, 71% come from just 50 questions, and inspection shows whole batches logged twice (every item doubled) or a worksheet cycling the same few items. Only 278 same-batch repeats change answer. **Dedup rule:** within a student and batch timestamp, keep the first occurrence of each (question, response) pair; drop the rest. This removes ~90k interactions (about 2% of train) and applies to every analysis and to any model we train. KTCF's published model was trained with these duplicates present.
- **Clean table** (`src/audit/reconstruct.py` → `data/processed/xes3g5m_clean.parquet`; counts in `reconstruct_log.json`): 7,295,810 raw cells → 5,549,184 after padding → 5,492,238 after batch dedup (56,946 removed, of which 819 were same-batch repeats with a different response, dropped and logged) → 5,491,578 after excluding 2 pre-2019 students. Final: 14,452 train students / 4,400,640 interactions; 3,612 test students / 1,090,938 interactions.
- **Repeats, after dedup.** Defined only across batches (strictly later timestamp). Train: 146,875 repeat events (3.34% of interactions), 81.4% of students have ≥ 1; 37,676 corrections (re-attempt correct 77.5%), 109,199 reviews (still correct 92.8%). Test: 36,931 events (3.39%), 80.9% of students; 9,499 corrections (77.2%), 27,432 reviews (93.2%). Gap classes, both splits: < 1 h ~35%, < 1 d ~35%, < 7 d ~17%, 7 d+ ~13%. About 94% of repeats are second attempts. Figures are raw and unmatched; matched versions come from Phase 3.
- **Item difficulty** (`src/audit/difficulty.py` → `data/processed/item_difficulty.csv`): 1 − first-attempt accuracy on train, questions with ≥ 30 first attempts (5,957 of 7,651). Terciles: easy ≤ 0.126, medium 0.126–0.265, hard > 0.265 (1,986 / 1,985 / 1,986 questions). 1,694 questions have no tercile (sparse or test-only) and are excluded from difficulty-stratified analyses.
- No difficulty field; difficulty is computed from item accuracy on training folds (`src/audit/difficulty.py`).

### ASSISTments 2009 and 2012 (secondary: re-attempts are a platform feature)

| | |
| --- | --- |
| Source | Official ASSISTments data releases; use the pyKT download instructions so the files match pyKT's loaders. Record the exact URL used in the checksum table below. |
| Licence | Research use per the ASSISTments data terms; check the terms page at download time and note the date. |
| Unpack to | `data/raw/assistments2009/`, `data/raw/assistments2012/` |
| Why | Skill-builder problem sets require retrying until correct, so correction re-attempts are common. Raw per-interaction logs with timestamps and attempt counts. |

### EdNet-KT1 (secondary: large-scale, heavy repetition)

| | |
| --- | --- |
| Source | Riiid EdNet release, KT1 subset; use the pyKT download instructions. Record the exact URL below. |
| Licence | CC BY-NC 4.0 (verify at download time). |
| Unpack to | `data/raw/ednet-kt1/` |
| Why | Largest public KT log; students repeat TOEIC practice items. Raw per-interaction logs. Large (tens of GB uncompressed); load in chunks or subsample students, see `src/audit/ednet_subsample.py`. |

## Checksums

Fill in after download so everyone can confirm they have identical files. Compute with `shasum -a 256 <file>`.

| Dataset | File | SHA-256 | Downloaded by | Date | URL used |
| --- | --- | --- | --- | --- | --- |
| XES3G5M | XES3G5M.tar | b9af3f29e5198a6f37a4e6c59d3e1db0a6eeb6d955c9697a26689649dfb78e05 | LJ | 2026-10-25 | the Google Drive link from https://github.com/ai4ed/XES3G5M|
| XES3G5M | question_level/train_valid_sequences_quelevel.csv | 52bb050fbdb3f35cab3fe9e50f58d258d0e8e1794231f9b9026416917166ec83 | LJ | 2026-10-25 | the Google Drive link from https://github.com/ai4ed/XES3G5M|
| XES3G5M | question_level/test_quelevel.csv | 60fee6ceffa8880ba5dcfec37be5a577740793afee4c86c3a4a3a91df0a4c4a3 | LJ | 2026-10-25 | the Google Drive link from https://github.com/ai4ed/XES3G5M|
| XES3G5M | metadata/questions.json | 57a3a63ef924e1f10bc83e673213841be4885f5ad52f0e606775a4fc030bc0d4 | LJ | 2026-10-25 | the Google Drive link from https://github.com/ai4ed/XES3G5M|
| ASSISTments 2009 | | | | | |
| ASSISTments 2012 | | | | | |
| EdNet-KT1 | | | | | |

## Related code, not data

- KTCF reference implementation: https://github.com/woojinkim1021/ktcf — cloned as a sibling folder (`../ktcf`), not inside this repo. Its `data/XES3G5M/metadata/` contains the English KC name map.
- pyKT: added as an editable dependency via `uv`; see `SETUP.md`.

## Rules

1. Never edit anything under `data/raw/`. If a file needs fixing, write a script in `src/` that reads raw and writes to `processed/`.
2. Every file in `data/processed/` must be reproducible by one command listed in the top-level README.
3. Do not commit data, even small extracts. Commit the script that makes the extract.
4. Keep this repo out of iCloud/Dropbox-synced folders.
5. No non-public data goes in this folder without a written data agreement and a note here on its terms.
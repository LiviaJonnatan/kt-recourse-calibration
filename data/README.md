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

**Files we use**

- `question_level/train_valid_sequences_quelevel.csv` and `question_level/test_quelevel.csv` for the audit and all models. Columns: `fold, uid, questions, concepts, responses, timestamps, selectmasks, is_repeat`. Sequence columns are comma-joined strings; multi-KC questions use `_` inside `concepts`.
- `metadata/questions.json` for question text, `kc_routes`, answer, `type` (0 = fill-in-the-blank, 1 = multiple-choice), and `analysis`.
- `metadata/kc_routes_map.json` for KC id → name. An English translation ships with the KTCF repo (see below).

**Things to know before using it**

- There is **no raw interaction table**. The release is already pyKT-preprocessed: sequences are cut into subsequences of length 200, split into 5 folds plus a fixed test set. The maintainers state the original table cannot be reconstructed. Full histories are approximated by concatenating a `uid`'s subsequences in timestamp order (`src/audit/reconstruct.py`).
- The `is_repeat` column does **not** mean a student re-attempted a question. It marks continuation rows of a multi-KC question in the KC-level files. Never use it to find re-attempts.
- The KC-level files expand one question into several rows; use the question-level files for anything that counts interactions.
- Timestamps are milliseconds.
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
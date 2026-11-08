"""Stage 1 (ASSISTments 2012-13) - same event-table schema as the other two datasets.

Mapping
    question = problem_id; area = skill_id; response = 1[correct == 1] (partial credit -> 0)
    ts = start_time; split = by learner (80/20 hashed), with the learner's whole sequence in one split
    mastery = 1 if the problem set type is Mastery (skill builder) -- the ASSISTments analogue of
              Duolingo's 'practice' session; kept as a column, not a feature
    single = 1 if problem_type == choose_1
Extras kept (not in the shared feature set): hint_count, attempt_count, ms_first_response.
HLR-style features reuse the theta fitted on Duolingo traces (p_hlr); it is a baseline, not a fit here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from s1_events import next_area_acc, rolling_prev_acc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, required=True, help="assist2012_slim_csv.gz")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--window", type=int, default=5)
    ap.add_argument("--theta", type=Path, default=None)
    ap.add_argument("--min_len", type=int, default=20)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(a.raw, usecols=["user_id", "problem_id", "skill_id", "correct", "start_time", "problem_type",
                                    "hint_count", "attempt_count", "ms_first_response", "type"])
    log = {"rows_raw": len(d)}
    d = d.dropna(subset=["skill_id", "start_time", "correct"])
    d["ts"] = (pd.to_datetime(d["start_time"], errors="coerce").astype("int64") // 10**6)
    d = d[d["ts"].notna()]
    d["uid"] = d["user_id"].astype(int)
    d["question"] = d["problem_id"].astype(np.int32)
    d["area"] = d["skill_id"].astype(int).astype(str)
    d["response"] = (d["correct"] >= 1.0).astype(np.int8)
    d["single"] = (d["problem_type"] == "choose_1").astype(np.int8)
    d["mastery"] = (d["type"].astype(str).str.contains("Mastery")).astype(np.int8)
    d["rt"] = (d["ms_first_response"].fillna(0) / 1000.0).clip(0, 600).astype(np.float32)
    d = d.sort_values(["uid", "ts"], kind="stable").reset_index(drop=True)
    d = d.drop_duplicates(["uid", "ts", "question"], keep="first")
    lens = d.groupby("uid").size()
    d = d[d["uid"].isin(lens[lens >= a.min_len].index)].reset_index(drop=True)
    log["rows_clean"] = len(d); log["users"] = int(d["uid"].nunique())

    h = pd.util.hash_array(d["uid"].to_numpy(np.int64)) % 10
    d["split"] = np.where(h < 8, "train", "test"); d["fold"] = 0
    d["seq_pos"] = d.groupby("uid").cumcount().astype(np.int32)
    g = d.groupby(["uid", "question"], sort=False)
    d["n_attempt"] = g.cumcount().astype(np.int16)
    d["prev_resp"] = g["response"].shift(1); d["prev_ts"] = g["ts"].shift(1)
    d["seen"] = d["n_attempt"]; d["correct"] = (g["response"].cumsum() - d["response"]).astype(np.int16)
    d["wrong"] = (d["seen"] - d["correct"]).astype(np.int16)
    d["action"] = np.select([d["n_attempt"] == 0, d["prev_resp"] == 0, d["prev_resp"] == 1],
                            ["new", "correction", "review"], default="new")
    fa = d[(d["split"] == "train") & (d["n_attempt"] == 0)].groupby("question")["response"].agg(["mean", "size"])
    d["difficulty"] = d["question"].map((1 - fa["mean"]).where(fa["size"] >= 20)).astype(np.float32)
    d["hist"] = d["seq_pos"]
    rolling_prev_acc(d, ["uid"], 20, 5, "pre_all")
    rolling_prev_acc(d, ["uid", "area"], 10, 3, "pre_area")
    d["n_area"] = d.groupby(["uid", "area"], sort=False).cumcount().astype(np.int32)
    lag_days = (d["ts"] - d["prev_ts"]) / 86400000.0
    d["gap_log"] = np.where(d["n_attempt"] > 0, np.log10((lag_days * 86400).clip(lower=1)), 0.0).astype(np.float32)
    theta = np.array(json.load(open(a.theta))["theta"], np.float32) if a.theta else np.array([0.5, 1.0, 1.0, 0.55], np.float32)
    xh = np.stack([np.ones(len(d)), np.sqrt(1 + d["seen"]), np.sqrt(1 + d["correct"]), np.sqrt(1 + d["wrong"])], 1)
    d["p_hlr"] = np.where(d["n_attempt"] > 0, 2.0 ** (-lag_days.fillna(0) / (2.0 ** (xh @ theta))), np.nan).astype(np.float32)
    d["area"] = d["area"].astype("category")
    d["y_next"] = next_area_acc(d, a.window)
    d["session"] = np.where(d["mastery"] == 1, "practice", "lesson"); d["format"] = d["problem_type"].astype(str)
    d["exercise_id"] = d["seq_pos"]   # no exercise grouping; one problem per row

    log.update({"events_with_outcome": int(d["y_next"].notna().sum()), "action_counts": d["action"].value_counts().to_dict(),
                "repeat_share": float((d["action"] != "new").mean()), "n_areas": int(d["area"].nunique()),
                "mastery_share": float(d["mastery"].mean()), "window": a.window})
    keep = ["split", "fold", "uid", "seq_pos", "exercise_id", "session", "format", "question", "area", "response", "ts",
            "action", "n_attempt", "prev_resp", "gap_log", "hist", "pre_all", "pre_area", "n_area", "difficulty", "single",
            "seen", "correct", "wrong", "p_hlr", "rt", "mastery", "hint_count", "attempt_count", "y_next"]
    d["question_str"] = d["question"].astype(str)
    d[keep + ["question_str"]].to_parquet(a.out / "events.parquet", index=False)
    json.dump(log, open(a.out / "s1_log.json", "w"), indent=2); print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()

"""Stage 1 (SLAM) - build the same event table as s1_events.py from the Duolingo
2018 SLAM en_es track (train/dev/test + keys, v4.0 format).

Mapping (confirmed with the user)
    question  = lower-cased surface token
    area      = Universal POS tag of the token
    response  = 1 - error label
    ts        = days since the learner started, in seconds
    action    = new / correction / review by the learner's previous encounter with the token
    y_next    = accuracy over the next `--window` same-POS tokens in LATER exercises,
                excluding the same token
Extra columns kept: exercise_id, session (lesson/practice/test), format, split.
HLR-style features (for the spaced-repetition baseline and as a covariate):
    seen, correct, wrong = prior encounters / prior correct / prior wrong for this token
    p_hlr = 2^(-lag_days / h), h = 2^(theta . [1, sqrt(1+seen), sqrt(1+correct), sqrt(1+wrong)])
            theta is fitted in s0_hlr.py on the HLR 13M traces (en learners, es UI); if
            --theta is absent, the paper's qualitative default is used.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from s1_events import next_area_acc, rolling_prev_acc

DEFAULT_THETA = np.array([0.0, 0.0, 0.3, -0.3], np.float32)   # placeholder if s0_hlr not run


def parse(path: Path, key: Path | None, split: str) -> pd.DataFrame:
    labels = {}
    if key is not None:
        with open(key) as f:
            for line in f:
                a, b = line.split(); labels[a] = int(b)
    rows = []
    meta = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith("# prompt:"):
                continue
            if line.startswith("# user:"):
                meta = {}
                for kv in line[2:].split():
                    k, v = kv.split(":", 1); meta[k] = v
                continue
            p = line.split()
            tid, tok, pos = p[0], p[1].lower(), p[2]
            lab = int(p[-1]) if key is None else labels.get(tid, -1)
            rows.append((split, meta["user"], tid[:8], float(meta["days"]), meta["session"], meta["format"],
                         int(meta.get("time", "0")) if meta.get("time", "0").isdigit() else -1, tok, pos, 1 - lab))
    return pd.DataFrame(rows, columns=["split", "user", "exercise_id", "days", "session", "format", "rt",
                                       "question_str", "area", "response"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, required=True, help="dir with en_es_slam_20190204.{train,dev,test} and keys")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--window", type=int, default=5)
    ap.add_argument("--theta", type=Path, default=None, help="json with HLR theta from s0_hlr.py")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    r = a.raw
    d = pd.concat([
        parse(r / "en_es_slam_20190204.train", None, "train"),
        parse(r / "en_es_slam_20190204.dev", r / "en_es_slam_20190204_dev.key", "dev"),
        parse(r / "en_es_slam_20190204.test", r / "en_es_slam_20190204_test.key", "test"),
    ], ignore_index=True)
    d = d[d["response"] >= 0]
    log = {"tokens": len(d), "users": int(d["user"].nunique()), "exercises": int(d["exercise_id"].nunique())}

    d["uid"] = d["user"].astype("category").cat.codes.astype(np.int32)
    d["question"] = d["question_str"].astype("category").cat.codes.astype(np.int32)
    d["ts"] = (d["days"] * 86400 * 1000).astype(np.int64)
    d = d.sort_values(["uid", "ts", "exercise_id"], kind="stable").reset_index(drop=True)
    d["seq_pos"] = d.groupby("uid").cumcount().astype(np.int32)
    d["single"] = (d["format"] == "reverse_tap").astype(np.int8)       # closest analogue of a closed-form item
    d["fold"] = 0

    g = d.groupby(["uid", "question"], sort=False)
    d["n_attempt"] = g.cumcount().astype(np.int16)
    d["prev_resp"] = g["response"].shift(1)
    d["prev_ts"] = g["ts"].shift(1)
    d["seen"] = d["n_attempt"]
    d["correct"] = (g["response"].cumsum() - d["response"]).astype(np.int16)
    d["wrong"] = (d["seen"] - d["correct"]).astype(np.int16)
    d["action"] = np.select([d["n_attempt"] == 0, d["prev_resp"] == 0, d["prev_resp"] == 1],
                            ["new", "correction", "review"], default="new")

    fa = d[(d["split"] == "train") & (d["n_attempt"] == 0)].groupby("question")["response"].agg(["mean", "size"])
    diff = (1 - fa["mean"]).where(fa["size"] >= 30)
    d["difficulty"] = d["question"].map(diff).astype(np.float32)

    d["hist"] = d["seq_pos"]
    rolling_prev_acc(d, ["uid"], 20, 5, "pre_all")
    rolling_prev_acc(d, ["uid", "area"], 10, 3, "pre_area")
    d["n_area"] = d.groupby(["uid", "area"], sort=False).cumcount().astype(np.int32)
    lag_days = (d["ts"] - d["prev_ts"]) / 86400000.0
    d["gap_log"] = np.where(d["n_attempt"] > 0, np.log10((lag_days * 86400).clip(lower=1)), 0.0).astype(np.float32)

    theta = np.array(json.load(open(a.theta))["theta"], np.float32) if a.theta else DEFAULT_THETA
    xh = np.stack([np.ones(len(d)), np.sqrt(1 + d["seen"]), np.sqrt(1 + d["correct"]), np.sqrt(1 + d["wrong"])], 1)
    h = 2.0 ** (xh @ theta)
    d["p_hlr"] = np.where(d["n_attempt"] > 0, 2.0 ** (-lag_days.fillna(0) / h), np.nan).astype(np.float32)

    # outcome window over LATER exercises only: temporarily collapse same-exercise tokens
    d["area"] = d["area"].astype("category")
    d["y_next"] = next_area_acc_later(d, a.window)

    log.update({"events_total": len(d), "events_with_outcome": int(d["y_next"].notna().sum()),
                "action_counts": d["action"].value_counts().to_dict(),
                "repeat_share": float((d["action"] != "new").mean()), "n_areas": int(d["area"].nunique()),
                "session_counts": d["session"].value_counts().to_dict(), "window": a.window})
    keep = ["split", "fold", "uid", "seq_pos", "exercise_id", "session", "format", "question", "question_str", "area",
            "response", "ts", "action", "n_attempt", "prev_resp", "gap_log", "hist", "pre_all", "pre_area", "n_area",
            "difficulty", "single", "seen", "correct", "wrong", "p_hlr", "y_next"]
    d[keep].to_parquet(a.out / "events.parquet", index=False)
    json.dump(log, open(a.out / "s1_log.json", "w"), indent=2)
    print(json.dumps(log, indent=2))


def next_area_acc_later(d: pd.DataFrame, window: int) -> np.ndarray:
    """Like s1_events.next_area_acc but only counts tokens from strictly later exercises."""
    out = np.full(len(d), np.nan, dtype=np.float32)
    for _, g in d.groupby(["uid", "area"], sort=False, observed=True):
        idx = g.index.to_numpy(); qq = g["question"].to_numpy(); ex = g["exercise_id"].to_numpy()
        rr = g["response"].to_numpy().astype(np.float32); n = len(g)
        if n <= window:
            continue
        for i in range(n - 1):
            keep = (qq[i + 1:] != qq[i]) & (ex[i + 1:] != ex[i])
            r = rr[i + 1:][keep]
            if len(r) >= window:
                out[idx[i]] = r[:window].mean()
    return out


if __name__ == "__main__":
    main()

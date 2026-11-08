"""Stage 2 - the student model. Loads KTCF's released DKT checkpoint
(saved_model/qid_model.ckpt, concept-level, emb/hidden 200, num_c 865) without
PyTorch and runs the forward pass in NumPy, so the baselines are scored by the
*same* model KTCF used. Nothing is retrained; this stage exists so stages 4-5 can
ask the published model the same questions KTCF asks it.

Also writes, for every test interaction, the DKT's predicted P(correct) on that
row's first KC given the true history (p_dkt). Used by stage 3 as a covariate
and by stage 4 as the "predicted-correctness" ranking signal.

Usage
    python s2_dkt.py --ckpt ../../repo_ktcf/saved_model/qid_model.ckpt --events ../out/events.parquet --out ../out
"""
from __future__ import annotations

import argparse
import pickle
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

NUM_C, H = 865, 200


class _Store:
    def __init__(self, z: zipfile.ZipFile, prefix: str):
        self.z, self.prefix = z, prefix

    def load(self, key: str, dtype) -> np.ndarray:
        return np.frombuffer(self.z.read(f"{self.prefix}/data/{key}"), dtype=dtype)


class _Unpickler(pickle.Unpickler):
    """Minimal torch-free unpickler for state_dicts: rebuilds tensors as ndarrays."""
    def __init__(self, f, store: _Store):
        super().__init__(f)
        self.store = store

    def persistent_load(self, pid):
        _, storage_type, key, _, _ = pid
        dt = {"FloatStorage": np.float32, "LongStorage": np.int64, "IntStorage": np.int32}[storage_type.__name__]
        return self.store.load(key, dt)

    def find_class(self, module, name):
        if name == "_rebuild_tensor_v2":
            def rebuild(storage, offset, size, stride, *_):
                n = int(np.prod(size)) if len(size) else 1
                return np.lib.stride_tricks.as_strided(
                    storage[offset:offset + n] if stride == tuple(np.cumprod((1,) + size[::-1][:-1])[::-1]) else storage[offset:],
                    shape=size, strides=tuple(s * storage.itemsize for s in stride)).copy()
            return rebuild
        if module.startswith("torch") and "Storage" in name:
            return type(name, (), {})
        if module == "collections" and name == "OrderedDict":
            import collections
            return collections.OrderedDict
        return super().find_class(module, name)


def load_dkt(ckpt: Path) -> dict:
    z = zipfile.ZipFile(ckpt)
    prefix = z.namelist()[0].split("/")[0]
    sd = _Unpickler(z.open(f"{prefix}/data.pkl"), _Store(z, prefix)).load()
    w = {k: np.asarray(v, dtype=np.float32) for k, v in sd.items()}
    assert w["interaction_emb.weight"].shape == (2 * NUM_C, H)
    return w


class DKT:
    """NumPy re-implementation of pyKT DKT (single-layer LSTM). Gates in PyTorch order i,f,g,o."""
    def __init__(self, w: dict):
        self.emb = w["interaction_emb.weight"]
        self.Wih = w["lstm_layer.weight_ih_l0"]          # (4H, H)
        self.Whh = w["lstm_layer.weight_hh_l0"]          # (4H, H)
        self.b = w["lstm_layer.bias_ih_l0"] + w["lstm_layer.bias_hh_l0"]
        self.Wo, self.bo = w["out_layer.weight"], w["out_layer.bias"]

    def hidden_states(self, c: np.ndarray, r: np.ndarray) -> np.ndarray:
        """c, r: int arrays (T,). Returns LSTM hidden states (T, H)."""
        x = self.emb[c + NUM_C * r]                       # (T, H)
        xw = x @ self.Wih.T + self.b                       # (T, 4H)
        h = np.zeros(H, np.float32); cst = np.zeros(H, np.float32)
        out = np.empty((len(c), H), np.float32)
        Whh_T = self.Whh.T
        for t in range(len(c)):
            g = xw[t] + h @ Whh_T
            i, f, gg, o = 1 / (1 + np.exp(-g[:H])), 1 / (1 + np.exp(-g[H:2 * H])), np.tanh(g[2 * H:3 * H]), 1 / (1 + np.exp(-g[3 * H:]))
            cst = f * cst + i * gg
            h = o * np.tanh(cst)
            out[t] = h
        return out

    def predict_all(self, c: np.ndarray, r: np.ndarray) -> np.ndarray:
        """P(correct) on every concept after each step: (T, NUM_C)."""
        hs = self.hidden_states(c, r)
        return 1 / (1 + np.exp(-(hs @ self.Wo.T + self.bo)))

    def predict_next(self, c: np.ndarray, r: np.ndarray) -> np.ndarray:
        """pyKT convention: prediction for row t uses history up to t-1 (row 0 undefined -> NaN)."""
        p = self.predict_all(c[:-1], r[:-1])
        out = np.full(len(c), np.nan, np.float32)
        out[1:] = p[np.arange(len(c) - 1), c[1:]]
        return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--events", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--split", default="test")
    a = ap.parse_args()
    dkt = DKT(load_dkt(a.ckpt))
    d = pd.read_parquet(a.events)
    d = d[d["split"] == a.split].sort_values(["uid", "seq_pos"])
    p = np.full(len(d), np.nan, np.float32)
    pos = 0
    for uid, g in d.groupby("uid", sort=False):
        c = g["first_kc"].to_numpy(np.int64); r = g["response"].to_numpy(np.int64)
        p[pos:pos + len(g)] = dkt.predict_next(c, r)
        pos += len(g)
    out = d[["uid", "seq_pos"]].copy(); out["p_dkt"] = p
    out.to_parquet(a.out / f"p_dkt_{a.split}.parquet", index=False)
    m = out["p_dkt"].notna()
    y = d.loc[m, "response"].to_numpy(); pp = out.loc[m, "p_dkt"].to_numpy()
    from sklearn.metrics import roc_auc_score
    print(f"{a.split}: n={m.sum()} AUC={roc_auc_score(y, pp):.4f} ACC={((pp > .5) == y).mean():.4f}")


if __name__ == "__main__":
    main()

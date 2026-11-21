"""Trained garment heads: small linear classifiers on the FashionCLIP image embedding.

One file format for Colab (training) and the Mac (inference), numpy + safetensors only, so the
notebook uploads this same file. Each head is softmax(W·x + b) over its labels.

A head (or one label of it) is used only where it was measured to beat what the Mac does today
on your own labeled photos. That decision is stored per head in heads.json `gate`, and
`allowed()` re-checks it here, so a hand-edited file can't switch anything on.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

WEIGHTS_FILE = "heads.safetensors"
META_FILE = "heads.json"
MIN_N = 5  # labeled photos of yours a label needs before it can be trusted
MIN_PRECISION = 0.70  # right this often when it's suggested, on your photos


@dataclass(frozen=True)
class Head:
    name: str  # category | type | pattern | fit/tops | fit/bottoms
    labels: tuple[str, ...]
    w: NDArray[np.float32]  # [K, D]
    b: NDArray[np.float32]  # [K]
    min_p: float  # don't suggest below this probability

    def probs(self, x: NDArray[np.float32]) -> NDArray[np.float64]:
        z = self.w.astype(np.float64) @ np.asarray(x, dtype=np.float64) + self.b
        z = np.exp(z - z.max())
        return np.asarray(z / z.sum(), dtype=np.float64)

    def predict(self, x: NDArray[np.float32]) -> tuple[str, float]:
        p = self.probs(x)
        k = int(np.argmax(p))
        return self.labels[k], float(p[k])


@dataclass(frozen=True)
class Heads:
    embedder: str
    heads: dict[str, Head]
    gate: dict[str, dict[str, Any]]  # per head: {"use": bool, "labels": [..], ...measurements}

    def allowed(self, head: str, label: str) -> bool:
        """True only if your photos showed this head beats today's guess, and for fit heads,
        this label was right ≥ MIN_PRECISION over ≥ MIN_N suggestions."""
        g = self.gate.get(head) or {}
        if not g.get("use") or head not in self.heads:
            return False
        if head.startswith("fit/"):
            r = (g.get("per_label") or {}).get(label) or {}
            return (
                int(r.get("suggested", 0)) >= MIN_N
                and float(r.get("precision", 0)) >= MIN_PRECISION
            )
        n, ours, today = int(g.get("n", 0)), g.get("accuracy"), g.get("baseline_accuracy")
        return n >= MIN_N and ours is not None and today is not None and float(ours) > float(today)

    def suggest(self, head: str, x: NDArray[np.float32]) -> str | None:
        h = self.heads.get(head)
        if h is None:
            return None
        label, p = h.predict(x)
        return label if p >= h.min_p and self.allowed(head, label) else None


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(folder: Path, embedder: str, heads: list[Head], extra: dict[str, Any]) -> Path:
    from safetensors.numpy import save_file

    folder.mkdir(parents=True, exist_ok=True)
    tensors: dict[str, NDArray[Any]] = {}
    for h in heads:
        tensors[f"{h.name}.w"] = np.ascontiguousarray(h.w, dtype=np.float32)
        tensors[f"{h.name}.b"] = np.ascontiguousarray(h.b, dtype=np.float32)
    wf = folder / WEIGHTS_FILE
    save_file(tensors, str(wf))
    meta = {
        "embedder": embedder,
        "sha256": sha256(wf),
        "heads": {h.name: {"labels": list(h.labels), "min_p": h.min_p} for h in heads},
        **extra,
    }
    (folder / META_FILE).write_text(json.dumps(meta, indent=2) + "\n")
    return folder / META_FILE


class HeadsError(Exception):
    pass


def load(folder: Path, embedder: str | None = None) -> Heads | None:
    """None when nothing is installed. Raises on a bad install or another embedder."""
    wf, mf = folder / WEIGHTS_FILE, folder / META_FILE
    if not wf.exists() or not mf.exists():
        return None
    from safetensors.numpy import load_file

    meta = json.loads(mf.read_text())
    if meta.get("sha256") != sha256(wf):
        raise HeadsError(f"{WEIGHTS_FILE} doesn't match the SHA-256 in {META_FILE}")
    if embedder is not None and meta.get("embedder") != embedder:
        raise HeadsError(f"heads were trained on {meta.get('embedder')}, not {embedder}")
    t = load_file(str(wf))
    heads = {}
    for name, h in meta["heads"].items():
        w, b = t[f"{name}.w"], t[f"{name}.b"]
        labels = tuple(h["labels"])
        if w.shape[0] != len(labels) or b.shape != (len(labels),):
            raise HeadsError(f"head {name}: weights don't match its labels")
        heads[name] = Head(name, labels, w, b, float(h.get("min_p", 0.5)))
    return Heads(str(meta["embedder"]), heads, dict(meta.get("gate") or {}))

"""Outfit compatibility head (SPEC 5.11): OutfitTransformer's scoring path, trained on Polyvore.

Only the small transformer head runs here. Its inputs are the FashionCLIP image embedding we
already store per piece (`item_embeddings`) and the FashionCLIP text embedding of
"{color} {type}", each 512-d, concatenated (same as owj0421/outfit-transformer @ eef4be55,
`OutfitCLIPTransformer.predict_score` with precomputed embeddings).

Safety and honesty:
- Weights load only from safetensors (no pickle), after a SHA-256 check against the config.
- The term counts only while `gate.json` is open, which `closet-worker compat-eval` writes
  after the model beats rules alone on your own logged outfits. Otherwise it changes nothing.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .candidates import Outfit
from .compat_head import HALF
from .model import Piece

log = logging.getLogger(__name__)

WEIGHTS_FILE = "compat_head.safetensors"
CONFIG_FILE = "compat_config.json"
GATE_FILE = "gate.json"
EMBEDDER = "patrickjohncyh/fashion-clip"

MIN_EVENTS = 30  # logged outfits needed before the gate can open
SKIP_CATEGORIES = frozenset({"Accessories"})  # Polyvore outfits are scored on main garments
BATCH = 256

TextEmbed = Callable[[list[str]], NDArray[np.float32]]


@dataclass(frozen=True)
class CompatConfig:
    n_head: int = 16
    d_ffn: int = 2024
    n_layers: int = 6
    dropout: float = 0.3
    max_items: int = 16
    text_template: str = "{color} {type}"
    embedder: str = EMBEDDER
    repo_commit: str = ""
    sha256: str = ""

    @staticmethod
    def from_json(d: dict[str, Any]) -> CompatConfig:
        known = CompatConfig.__dataclass_fields__
        return CompatConfig(**{k: v for k, v in d.items() if k in known})


def build_head(cfg: CompatConfig) -> Any:
    from .compat_head import build

    return build(n_head=cfg.n_head, d_ffn=cfg.d_ffn, n_layers=cfg.n_layers, dropout=cfg.dropout)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class CompatError(Exception):
    pass


def load_head(folder: Path) -> tuple[Any, CompatConfig] | None:
    """The head in eval mode, or None when no model is installed. Raises on a bad install."""
    wf, cf = folder / WEIGHTS_FILE, folder / CONFIG_FILE
    if not wf.exists() or not cf.exists():
        return None
    return _load_head(str(folder), wf.stat().st_mtime_ns, cf.stat().st_mtime_ns)


@lru_cache(maxsize=1)
def _load_head(folder_s: str, _w_mtime: int, _c_mtime: int) -> tuple[Any, CompatConfig]:
    """Cached per file version, so the worker loads the weights once, not per job."""
    from safetensors.torch import load_file

    folder = Path(folder_s)
    wf, cf = folder / WEIGHTS_FILE, folder / CONFIG_FILE

    cfg = CompatConfig.from_json(json.loads(cf.read_text()))
    if not cfg.sha256 or sha256(wf) != cfg.sha256:
        raise CompatError(f"{WEIGHTS_FILE} doesn't match the SHA-256 in {CONFIG_FILE}")
    if cfg.embedder != EMBEDDER:
        raise CompatError(f"model expects {cfg.embedder} embeddings, not {EMBEDDER}")
    head = build_head(cfg)
    head.load_state_dict(load_file(str(wf)), strict=True)
    return head.eval(), cfg


@dataclass(frozen=True)
class Gate:
    open: bool
    n: int = 0
    hit_rules: float | None = None
    hit_compat: float | None = None
    measured_at: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "open": self.open,
            "n": self.n,
            "hit_rules": self.hit_rules,
            "hit_compat": self.hit_compat,
            "measured_at": self.measured_at,
        }


def read_gate(folder: Path) -> Gate:
    try:
        d = json.loads((folder / GATE_FILE).read_text())
    except (OSError, ValueError):
        return Gate(open=False)
    n = int(d.get("n") or 0)
    hr, hc = d.get("hit_rules"), d.get("hit_compat")
    # Re-check the rule here so a hand-edited file can't open it.
    ok = (
        bool(d.get("open"))
        and n >= MIN_EVENTS
        and hr is not None
        and hc is not None
        and float(hc) > float(hr)
    )
    return Gate(ok, n, hr, hc, d.get("measured_at"))


def decide_gate(n: int, hit_rules: float, hit_compat: float, measured_at: str) -> Gate:
    return Gate(n >= MIN_EVENTS and hit_compat > hit_rules, n, hit_rules, hit_compat, measured_at)


def status(folder: Path) -> dict[str, Any]:
    """For the heartbeat: whether a model is installed, the gate, and the logged count."""
    installed = (folder / WEIGHTS_FILE).exists() and (folder / CONFIG_FILE).exists()
    g = read_gate(folder)
    return {"installed": installed, "on": installed and g.open, "n": g.n, "need": MIN_EVENTS}


def describe(p: Piece, cfg: CompatConfig) -> str:
    color = p.color_name or ""
    kind = p.type or p.name.lower()
    return " ".join(cfg.text_template.format(color=color, type=kind).split())


class CompatScorer:
    """Scores many outfits in batches. Outfits with a piece we can't embed get no score."""

    def __init__(
        self,
        head: Any,
        cfg: CompatConfig,
        image_vecs: Mapping[str, Sequence[float]],
        text_embed: TextEmbed,
    ) -> None:
        self.head, self.cfg = head, cfg
        self.image = {k: np.asarray(v, dtype=np.float32) for k, v in image_vecs.items()}
        self.text_embed = text_embed
        self._text: dict[str, NDArray[np.float32]] = {}

    def _texts(self, pieces: list[Piece]) -> None:
        want = sorted({describe(p, self.cfg) for p in pieces} - self._text.keys())
        if want:
            for s, v in zip(want, self.text_embed(want), strict=True):
                self._text[s] = np.asarray(v, dtype=np.float32)

    def _vec(self, p: Piece) -> NDArray[np.float32] | None:
        img = self.image.get(p.id)
        if img is None or img.shape != (HALF,):
            return None
        return np.concatenate([img, self._text[describe(p, self.cfg)]])

    def scores(self, outfits: Sequence[Outfit]) -> list[float | None]:
        """compat(o) = 2·p − 1 in [-1, 1], or None when it can't be computed."""
        import torch

        main = [[p for p in o if p.category not in SKIP_CATEGORIES] for o in outfits]
        self._texts([p for ps in main for p in ps])
        rows: list[NDArray[np.float32] | None] = []
        for ps in main:
            vs = [self._vec(p) for p in ps][: self.cfg.max_items]
            rows.append(None if len(vs) < 2 or any(v is None for v in vs) else np.stack(vs))  # type: ignore[arg-type]
        out: list[float | None] = [None] * len(rows)
        idx = [i for i, r in enumerate(rows) if r is not None]
        for start in range(0, len(idx), BATCH):
            chunk = idx[start : start + BATCH]
            n = max(rows[i].shape[0] for i in chunk)  # type: ignore[union-attr]
            x = np.zeros((len(chunk), n, 2 * HALF), dtype=np.float32)
            lengths = np.zeros(len(chunk), dtype=np.int64)
            for j, i in enumerate(chunk):
                r = rows[i]
                assert r is not None
                x[j, : len(r)] = r
                lengths[j] = len(r)
            with torch.no_grad():
                p = self.head(torch.from_numpy(x), torch.from_numpy(lengths)).numpy()
            for j, i in enumerate(chunk):
                out[i] = round(float(2 * p[j] - 1), 4)
        return out


def open_scorer(
    folder: Path,
    image_vecs: Callable[[], Mapping[str, Sequence[float]]],
    text_embed: Callable[[], TextEmbed],
    *,
    require_gate: bool = True,
) -> CompatScorer | None:
    """A scorer when a model is installed (and the gate is open, unless require_gate=False)."""
    if require_gate and not read_gate(folder).open:
        return None
    try:
        loaded = load_head(folder)
    except CompatError as e:
        log.warning("outfit model not used: %s", e)
        return None
    if loaded is None:
        return None
    head, cfg = loaded
    return CompatScorer(head, cfg, image_vecs(), text_embed())

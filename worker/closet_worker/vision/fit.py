"""Fit from a photo (slim, oversized, flared, wide…): outline measurements + the photo model.

Two independent reads:
- **Shape** from the cut-out outline of a flat-lay photo. Pants: how the leg width changes from
  thigh to knee to hem (taper, straight, wide, flare). Tops: body width near the hem compared
  with the length (narrow, regular, wide, short).
- **Photo model**: FashionCLIP zero-shot over this category's fit choices ("flared jeans" vs
  "skinny jeans"…).

The guess is the photo model's pick when the shape agrees, or when the shape can't tell (a fit
with no shape rule, or no usable outline) and the photo model is fairly sure. Otherwise: no guess.

Nothing here is trusted until measured. The tagging eval reports how often each fit is right on
your own labeled photos, and tag_item only suggests fits that passed (vocab/fits.yaml `gate`).
Hanger and folded photos hide the shape, so ask for flat-lays.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from numpy.typing import NDArray

from .embed import Embedder

FITS_FILE = Path(__file__).resolve().parent.parent / "vocab" / "fits.yaml"
WEARS = ("menswear", "womenswear", "both")
PHOTO_ONLY_MIN_P = 0.5  # photo model alone must be at least this sure

# Outline thresholds. Starting values from typical garment proportions, not measured on your
# clothes: the eval prints each labeled fit's measurements so these can be tuned honestly.
PANTS_FLARE = 1.15  # hem / knee width at or above: flare (or bootcut)
PANTS_TAPER = 0.85  # hem / knee width at or below: taper (skinny, slim)
PANTS_WIDE = 0.60  # knee width (both legs) / length at or above, with no taper: wide
TOP_NARROW = 0.66  # body width near the hem / length below: narrow
TOP_WIDE = 0.80  # above: wide
TOP_SHORT = 1.05  # above: short (cropped)


@dataclass(frozen=True)
class Fit:
    id: str
    label: str
    wears: tuple[str, ...]
    prompt: str
    shape: str | None


@dataclass(frozen=True)
class FitGroup:
    name: str
    categories: tuple[str, ...]
    fits: tuple[Fit, ...]


@dataclass(frozen=True)
class FitVocab:
    groups: tuple[FitGroup, ...]
    min_precision: float
    min_n: int

    def group_for(self, category: str | None) -> FitGroup | None:
        return next((g for g in self.groups if category in g.categories), None)


@cache
def load_fits(path: Path = FITS_FILE) -> FitVocab:
    d = yaml.safe_load(path.read_text())
    groups = tuple(
        FitGroup(
            name=name,
            categories=tuple(g["categories"]),
            fits=tuple(
                Fit(f["id"], f["label"], tuple(f["wears"]), f["prompt"], f.get("shape"))
                for f in g["fits"]
            ),
        )
        for name, g in d["groups"].items()
    )
    gate = d.get("gate") or {}
    return FitVocab(groups, float(gate.get("min_precision", 0.7)), int(gate.get("min_n", 5)))


def options(category: str | None, wears: str | None, v: FitVocab | None = None) -> list[Fit]:
    """The fit choices for a category. No profile answer (or "both") shows every choice."""
    g = (v or load_fits()).group_for(category)
    if g is None:
        return []
    if wears not in ("menswear", "womenswear"):
        return list(g.fits)
    return [f for f in g.fits if wears in f.wears]


# ---------------------------------------------------------------- outline


def _band(widths: NDArray[np.float64], lo: float, hi: float) -> float:
    n = len(widths)
    a, b = int(n * lo), max(int(n * lo) + 1, int(n * hi))
    return float(np.median(widths[a:b]))


def _center_run(row: NDArray[np.bool_]) -> int:
    """Length of the mask run nearest the row's middle (the body, not a sleeve lying beside it)."""
    xs = np.flatnonzero(row)
    if len(xs) == 0:
        return 0
    splits = np.flatnonzero(np.diff(xs) > 1) + 1
    runs = np.split(xs, splits)
    mid = len(row) / 2

    def dist(r: NDArray[np.intp]) -> float:
        return 0.0 if r[0] <= mid <= r[-1] else float(min(abs(r[0] - mid), abs(r[-1] - mid)))

    best = min(runs, key=dist)
    return int(best[-1] - best[0] + 1)


def measure(mask: NDArray[np.bool_], group: str) -> dict[str, float] | None:
    """Outline ratios for pants or tops, or None when the outline is unusable."""
    ys, xs = np.nonzero(mask)
    if len(xs) < 500:
        return None
    m = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    h, w = m.shape
    if mask.all() or h < 40 or w < 20:  # no cut-out: the whole photo
        return None
    if group == "bottoms":
        widths = m.sum(axis=1).astype(np.float64)  # both legs together
        thigh = _band(widths, 0.30, 0.38)
        knee = _band(widths, 0.55, 0.65)
        hem = _band(widths, 0.90, 0.97)
        if knee <= 0 or thigh <= 0:
            return None
        return {
            "knee_thigh": round(knee / thigh, 3),
            "hem_knee": round(hem / knee, 3),
            "knee_len": round(knee / h, 3),
        }
    if group == "tops":
        rows = [_center_run(m[int(h * f)]) for f in (0.80, 0.85, 0.90)]
        body = float(np.median(rows))
        if body <= 0:
            return None
        return {"body_len": round(body / h, 3)}
    return None


def shape_of(features: dict[str, float] | None, group: str) -> str | None:
    if not features:
        return None
    if group == "bottoms":
        hk, kl = features["hem_knee"], features["knee_len"]
        if hk >= PANTS_FLARE:
            return "flare"
        if hk <= PANTS_TAPER:
            return "taper"
        return "wide" if kl >= PANTS_WIDE else "straight"
    if group == "tops":
        r = features["body_len"]
        if r > TOP_SHORT:
            return "short"
        if r > TOP_WIDE:
            return "wide"
        return "narrow" if r < TOP_NARROW else "regular"
    return None


# ---------------------------------------------------------------- photo model + combination


@dataclass
class FitGuess:
    fit: str | None  # the guess, or None when the two reads don't support one
    method: str  # both | photo | none
    photo_fit: str | None = None
    photo_p: float = 0.0
    shape: str | None = None
    features: dict[str, float] | None = None
    ranked: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "fit": self.fit,
            "method": self.method,
            "photo_fit": self.photo_fit,
            "photo_p": round(self.photo_p, 4),
            "shape": self.shape,
            "features": self.features,
        }


def _noun(type_: str, group: str) -> str:
    t = type_.strip().lower()
    if t:
        return t
    return {"bottoms": "trousers", "tops": "shirt", "sets": "outfit"}.get(group, "garment")


def combine(
    fits: list[Fit], probs: NDArray[np.float64], shape: str | None
) -> tuple[str | None, str]:
    k = int(np.argmax(probs))
    top, p = fits[k], float(probs[k])
    if shape is not None and top.shape == shape:
        return top.id, "both"
    shape_silent = shape is None or top.shape is None
    if shape_silent and p >= PHOTO_ONLY_MIN_P:
        return top.id, "photo"
    return None, "none"


def guess_fit(
    image_vec: NDArray[np.float32],
    mask: NDArray[np.bool_] | None,
    category: str | None,
    type_: str,
    wears: str | None,
    emb: Embedder,
) -> FitGuess | None:
    """None when fit doesn't apply (shoes, accessories) or the category has no choices."""
    v = load_fits()
    g = v.group_for(category)
    fits = options(category, wears, v)
    if g is None or len(fits) < 2:
        return None
    noun = _noun(type_, g.name)
    vecs = emb.text([f"a photo of {f.prompt} {noun}" for f in fits])
    logits = emb.logit_scale * (vecs @ image_vec)
    z = np.exp(logits - logits.max())
    probs = z / z.sum()
    feats = measure(mask, g.name) if mask is not None else None
    shape = shape_of(feats, g.name)
    fit, method = combine(fits, probs, shape)
    k = int(np.argmax(probs))
    return FitGuess(
        fit=fit,
        method=method,
        photo_fit=fits[k].id,
        photo_p=float(probs[k]),
        shape=shape,
        features=feats,
        ranked=[{"fit": f.id, "p": round(float(q), 4)} for f, q in zip(fits, probs, strict=True)],
    )


# ---------------------------------------------------------------- gate (from the tagging eval)


def gate_key(category: str | None, fit: str) -> str | None:
    g = load_fits().group_for(category)
    return None if g is None else f"{g.name}/{fit}"


def read_gate(path: Path, model: str | None = None) -> frozenset[str]:
    """Fits ("bottoms/flare") the eval measured as right often enough on your photos.

    Measured with another embedding model? Then nothing counts: the numbers don't carry over.
    """
    try:
        d = json.loads(path.read_text())
    except (OSError, ValueError):
        return frozenset()
    if model is not None and d.get("model") not in (None, model):
        return frozenset()
    v = load_fits()
    ok = set()
    for key, r in (d.get("per_fit") or {}).items():
        # Re-check here so a hand-edited list can't switch a fit on.
        n, prec = int(r.get("suggested", 0)), float(r.get("precision", 0.0))
        if n >= v.min_n and prec >= v.min_precision:
            ok.add(str(key))
    return frozenset(ok)

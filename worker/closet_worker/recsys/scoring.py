"""Rule score (SPEC 5.4 step 3). Each term returns (value, reasons); weights in weights.yaml."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from numpy.typing import NDArray

from closet_worker.vision.color import delta_e, hex_to_rgb, srgb_to_lab

from .candidates import FORMALITY_TARGET, Outfit, needs_layer
from .model import WARMTH_LEVEL, Context, History, Piece

NEUTRAL_CHROMA = (
    14.0  # below this CIELAB chroma a color reads as neutral (navy, grey, beige, white…)
)
FRESH_DAYS = 14  # a piece unworn this long counts as fully fresh
NEVER_WORN_DAYS = 30
RECENT_PIECE_DAYS = 2
RECENT_OUTFIT_DAYS = 7

Reason = dict[str, Any]


@cache
def weights() -> dict[str, float]:
    return {
        k: float(v)
        for k, v in yaml.safe_load((Path(__file__).parent / "weights.yaml").read_text()).items()
    }


def _chroma_hue(lab: tuple[float, float, float]) -> tuple[float, float]:
    _, a, b = lab
    return math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


# Menswear neutrals: they pair with anything even though some (navy, khaki, brown) have real chroma.
NEUTRAL_NAMES = frozenset(
    {
        "black",
        "charcoal",
        "grey",
        "light grey",
        "silver",
        "white",
        "off-white",
        "ivory",
        "cream",
        "beige",
        "stone",
        "khaki",
        "tan",
        "camel",
        "brown",
        "chocolate",
        "navy",
        "indigo",
        "denim",
        "olive",
    }
)


def is_neutral(p: Piece, lab: tuple[float, float, float]) -> bool:
    if p.color_name:
        return p.color_name in NEUTRAL_NAMES
    return _chroma_hue(lab)[0] < NEUTRAL_CHROMA


def harmony(o: Outfit) -> tuple[float, list[Reason]]:
    """Neutrals go with anything; at most 2 saturated hues; analogous/complementary get extra."""
    labs = [(p, p.lab) for p in o]
    known = [(p, lab) for p, lab in labs if lab is not None]
    if not known:
        return 0.0, []
    sat = [(p, _chroma_hue(lab)[1]) for p, lab in known if not is_neutral(p, lab)]
    reasons: list[Reason] = []
    main = [p for p in o if p.category in ("Tops", "Bottoms", "Sets & suits") and p.color_name]
    if len(main) >= 2 and main[0].color_name != main[1].color_name:
        reasons.append({"kind": "pair", "a": main[0].color_name, "b": main[1].color_name})
    if len(sat) > 2:
        return -1.0, []
    if len(sat) <= 1:
        return (0.4 if not sat else 0.6), reasons
    d = abs(sat[0][1] - sat[1][1]) % 360
    d = min(d, 360 - d)
    if d <= 40 or d >= 150:  # analogous or complementary
        return 0.7, reasons
    return -0.3, []


PALETTE_NEAR = 40.0  # ΔE2000 at which closeness to your palette reaches 0
CAREFUL_NEAR = 12.0  # tops and layers this close to a "use carefully" color are penalized
BEST_MATCH = 10.0  # close enough to call it "one of your best colors"


@cache
def _labs(hexes: tuple[str, ...]) -> NDArray[np.float64]:
    return srgb_to_lab(np.array([hex_to_rgb(h) for h in hexes]))


def palette_fit(o: Outfit, analysis: dict[str, Any] | None) -> tuple[float, list[Reason]]:
    """Closeness to your best colors and neutrals; careful colors near the face cost a little."""
    if not analysis or not analysis.get("best"):
        return 0.0, []
    good = tuple(c["hex"] for c in [*analysis["best"], *analysis.get("neutrals", [])])
    best_names = {c["hex"]: c["name"] for c in analysis["best"]}
    careful = tuple(c["hex"] for c in analysis.get("careful", []))
    vals: list[float] = []
    reasons: list[Reason] = []
    for p in o:
        lab = p.lab
        if lab is None:
            continue
        here = np.array([lab])
        d = delta_e(np.repeat(here, len(good), axis=0), _labs(good))
        vals.append(1.0 - min(float(d.min()), PALETTE_NEAR) / PALETTE_NEAR)
        k = int(d.argmin())
        if (
            float(d[k]) <= BEST_MATCH
            and good[k] in best_names
            and p.category in ("Tops", "Layers")
            and not reasons
        ):
            reasons.append(
                {"kind": "palette", "color": best_names[good[k]].lower(), "piece": p.noun}
            )
        if careful and p.category in ("Tops", "Layers", "Sets & suits"):
            dc = delta_e(np.repeat(here, len(careful), axis=0), _labs(careful))
            if float(dc.min()) <= CAREFUL_NEAR:
                vals.append(-0.6)
    if not vals:
        return 0.0, []
    return max(-1.0, min(1.0, sum(vals) / len(vals))), reasons


def formality(o: Outfit, ctx: Context, shift: int = 0) -> tuple[float, list[Reason]]:
    fs = [p.formality for p in o if p.formality is not None]
    if not fs:
        return 0.0, []
    target = FORMALITY_TARGET.get(ctx.occasion, 3.0) + shift
    spread = max(fs) - min(fs)
    mean = sum(fs) / len(fs)
    v = 1.0 - 0.3 * spread - 0.45 * abs(mean - target)
    reasons: list[Reason] = [{"kind": "formal_up"}] if shift > 0 and mean >= target - 0.5 else []
    return max(-1.0, min(1.0, v)), reasons


def _is_rain_risk(p: Piece) -> bool:
    t = p.type
    return (
        "suede" in t
        or t == "white sneakers"
        or (p.category == "Shoes" and "sneaker" in t and p.color_name == "white")
    )


def weather(o: Outfit, ctx: Context) -> tuple[float, list[Reason]]:
    if ctx.temp_high_f is None and ctx.rain_pct < 50:
        return 0.0, []
    v = 0.0
    reasons: list[Reason] = []
    if ctx.temp_high_f is not None:
        t = ctx.temp_high_f
        want = 0.0 if t >= 75 else 0.5 if t >= 65 else 1.0 if t >= 50 else 2.0
        levels = [WARMTH_LEVEL[p.warmth] for p in o if p.warmth in WARMTH_LEVEL]
        have = max(levels) if levels else 1.0
        v = 1.0 - abs(have - want) / 2
        layer = next((p for p in o if p.category == "Layers"), None)
        if layer and needs_layer(ctx) and t < 60:
            reasons.append({"kind": "weather", "piece": layer.noun, "temp": ctx.temp_text()})
    if ctx.rain_pct >= 50:
        risky = [p for p in o if _is_rain_risk(p)]
        if risky:
            v -= 0.8
        else:
            reasons.append({"kind": "rain"})
    return max(-1.0, min(1.0, v)), reasons


def freshness(o: Outfit, ctx: Context, h: History) -> tuple[float, list[Reason]]:
    """Favor pieces not worn lately; penalize repeats (pieces in 2 days, the outfit in 7)."""
    days = []
    for p in o:
        last = h.piece_last.get(p.id)
        days.append((p, NEVER_WORN_DAYS if last is None else (ctx.day - last).days))
    v = sum(min(d, FRESH_DAYS) / FRESH_DAYS for _, d in days) / len(days)
    if any(0 <= d <= RECENT_PIECE_DAYS for _, d in days):
        v -= 0.8
    last_outfit = h.outfit_last.get(frozenset(p.id for p in o))
    if last_outfit is not None and (ctx.day - last_outfit).days <= RECENT_OUTFIT_DAYS:
        v -= 1.5
    reasons: list[Reason] = []
    known = [(p, d) for p, d in days if p.id in h.piece_last and d >= 7]
    if known:
        p, d = max(known, key=lambda x: x[1])
        reasons.append({"kind": "fresh", "piece": p.noun, "days": d})
    elif all(p.id not in h.piece_last for p in o):
        reasons.append({"kind": "new"})
    return v, reasons


@dataclass
class Score:
    total: float
    terms: dict[str, float]
    reasons: list[Reason] = field(default_factory=list)


def score(
    o: Outfit,
    ctx: Context,
    h: History,
    shift: int = 0,
    profile: dict[str, Any] | None = None,
    compat: float | None = None,
) -> Score:
    """`compat` is the outfit model's term; pass it only while its gate is open (compat.py)."""
    w = weights()
    parts: dict[str, tuple[float, list[Reason]]] = {
        "harmony": harmony(o),
        "palette": palette_fit(o, profile),
        "formality": formality(o, ctx, shift),
        "weather": weather(o, ctx),
        "freshness": freshness(o, ctx, h),
    }
    if compat is not None:
        parts["compat"] = (compat, [])  # no reason text: the model can't say why
    terms = {k: round(v[0], 4) for k, v in parts.items()}
    total = sum(w.get(k, 0.0) * v for k, v in terms.items())
    reasons = [
        r for k in ("palette", "harmony", "freshness", "weather", "formality") for r in parts[k][1]
    ]
    return Score(round(total, 4), terms, reasons)


def days_since(d: date | None, today: date) -> int | None:
    return None if d is None else (today - d).days

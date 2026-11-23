"""Check my outfit: every check the ideas use, run on pieces you picked, each explained.

The verdict is plain words, never a made-up percentage:
- "Strong": every check that has data passes.
- "Works": only minor checks miss (a recent repeat, the weather).
- "Rethink": a core check misses (structure, colors, formality, palette near your face, fit).
Checks without data (no colors, no fits, no forecast, no style profile) are listed as "not checked"
with what would let them run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from closet_worker.vision.color import delta_e, hex_to_rgb, srgb_to_lab

from .candidates import FORMALITY_TARGET
from .engine import REPEAT_OUTFIT_DAYS, REPEAT_TOP_DAYS
from .model import Context, History, Piece
from .scoring import (
    BEST_MATCH,
    CAREFUL_NEAR,
    CLOSE_BOTTOM,
    CLOSE_TOP,
    LOOSE_BOTTOM,
    LOOSE_TOP,
    _chroma_hue,
    harmony,
    is_neutral,
    weather,
)

MINOR = frozenset({"freshness", "weather"})
OCCASION_WORD = {"office": "the office", "college": "college", "party": "a party", "home": "home"}


@dataclass
class Check:
    key: str
    label: str
    ok: bool | None  # None: not checked (no data)
    detail: str


def _names(ps: list[Piece]) -> str:
    n = [p.name.lower() for p in ps]
    return n[0] if len(n) == 1 else ", ".join(n[:-1]) + " and " + n[-1]


def structure(o: list[Piece]) -> Check:
    cats = {p.category for p in o}
    has_base = ("Tops" in cats and "Bottoms" in cats) or "Sets & suits" in cats
    missing = []
    if not has_base:
        missing.append("a top and a bottom" if "Sets & suits" not in cats else "")
    if "Shoes" not in cats:
        missing.append("shoes")
    missing = [m for m in missing if m]
    if missing:
        return Check("structure", "Complete outfit", False, f"Add {' and '.join(missing)}.")
    return Check("structure", "Complete outfit", True, "Top, bottom and shoes are all there.")


def colors(o: list[Piece]) -> Check:
    known = [(p, p.lab) for p in o if p.lab is not None]
    if len(known) < 2:
        return Check(
            "harmony", "Colors", None, "Add colors to the pieces to check how they go together."
        )
    v, _ = harmony(tuple(p for p, _ in known))
    bold = [p for p, lab in known if not is_neutral(p, lab)]
    if v < 0 and len(bold) > 2:
        return Check(
            "harmony",
            "Colors",
            False,
            f"Three or more accent colors compete ({_names(bold)}): keep one or two and let neutrals do the rest.",
        )
    if v < 0:
        return Check(
            "harmony",
            "Colors",
            False,
            f"The {_names(bold)} sit at an awkward distance on the color wheel: neither close nor opposite.",
        )
    if not bold:
        return Check("harmony", "Colors", True, "All neutrals: they go with each other.")
    if len(bold) == 1:
        return Check(
            "harmony",
            "Colors",
            True,
            f"One accent color, the {bold[0].name.lower()}, against neutrals.",
        )
    h1, h2 = (_chroma_hue(p.lab)[1] for p in bold[:2] if p.lab)
    d = min(abs(h1 - h2) % 360, 360 - abs(h1 - h2) % 360)
    how = (
        "close together on the color wheel" if d <= 40 else "opposite each other on the color wheel"
    )
    return Check("harmony", "Colors", True, f"The {_names(bold[:2])} are {how}, so they pair well.")


def near_face(o: list[Piece], analysis: dict[str, Any] | None) -> Check:
    face = [p for p in o if p.category in ("Tops", "Layers", "Sets & suits") and p.lab is not None]
    if not analysis or not analysis.get("best"):
        return Check(
            "palette",
            "Near your face",
            None,
            "Analyze your style photos to check colors against your palette.",
        )
    if not face:
        return Check(
            "palette", "Near your face", None, "Add colors to your top or layer to check them."
        )
    outer = next((p for p in face if p.category == "Layers"), face[0])
    lab = np.array([outer.lab])
    best = [(c["name"], c["hex"]) for c in analysis["best"]]
    neutrals = [(c["name"], c["hex"]) for c in analysis.get("neutrals", [])]
    careful = [(c["name"], c["hex"]) for c in analysis.get("careful", [])]

    def nearest(cs: list[tuple[str, str]]) -> tuple[str, float] | None:
        if not cs:
            return None
        d = delta_e(
            np.repeat(lab, len(cs), axis=0), srgb_to_lab(np.array([hex_to_rgb(h) for _, h in cs]))
        )
        k = int(np.argmin(d))
        return cs[k][0].lower(), float(d[k])

    c = nearest(careful)
    if c and c[1] <= CAREFUL_NEAR:
        return Check(
            "palette",
            "Near your face",
            False,
            f"The {outer.name.lower()} is close to {c[0]}, one of your “use carefully” colors, right by your face.",
        )
    b = nearest(best)
    if b and b[1] <= BEST_MATCH:
        return Check(
            "palette",
            "Near your face",
            True,
            f"The {outer.name.lower()} is close to {b[0]}, one of your best colors.",
        )
    n = nearest(neutrals)
    if n and n[1] <= BEST_MATCH:
        return Check(
            "palette",
            "Near your face",
            True,
            f"The {outer.name.lower()} is close to {n[0]}, one of your neutrals.",
        )
    return Check(
        "palette",
        "Near your face",
        False,
        f"The {outer.name.lower()} is far from your best colors and neutrals; one of those near your face works better.",
    )


def formality(o: list[Piece], occasion: str) -> Check:
    fs = [(p, p.formality) for p in o if p.formality is not None]
    if not fs:
        return Check("formality", "Formality", None, "Set formality on the pieces to check it.")
    target = FORMALITY_TARGET.get(occasion, 3.0)
    lo = min(fs, key=lambda x: x[1])
    hi = max(fs, key=lambda x: x[1])
    mean = sum(f for _, f in fs) / len(fs)
    where = OCCASION_WORD.get(occasion, occasion)
    if hi[1] - lo[1] >= 3:
        return Check(
            "formality",
            "Formality",
            False,
            f"The {lo[0].name.lower()} is much more casual than the {hi[0].name.lower()}: pick pieces closer in formality.",
        )
    if abs(mean - target) > 1.1:
        word = "too casual" if mean < target else "too dressed up"
        return Check("formality", "Formality", False, f"Overall it’s {word} for {where}.")
    return Check("formality", "Formality", True, f"The pieces match each other and suit {where}.")


def fit(o: list[Piece], occasion: str) -> Check:
    tops = [p for p in o if p.category in ("Tops", "Layers") and p.fit]
    bottoms = [p for p in o if p.category == "Bottoms" and p.fit]
    if not tops or not bottoms:
        return Check(
            "fit", "Fit balance", None, "Set the fit on your top and bottoms to check the balance."
        )
    t = next((p for p in tops if p.category == "Layers"), tops[0])
    b = bottoms[0]
    tf, bf = t.fit or "", b.fit or ""
    if tf in LOOSE_TOP and bf in LOOSE_BOTTOM and occasion != "home":
        return Check(
            "fit",
            "Fit balance",
            False,
            f"A {tf} {t.noun} over {bf} {b.noun}: loose over loose loses its shape. Swap one for a closer fit.",
        )
    if (tf in LOOSE_TOP and bf in CLOSE_BOTTOM) or (tf in CLOSE_TOP and bf in LOOSE_BOTTOM):
        return Check(
            "fit",
            "Fit balance",
            True,
            f"A {tf} {t.noun} with {bf} {b.noun} balances loose and close.",
        )
    return Check(
        "fit", "Fit balance", True, f"A {tf} {t.noun} with {bf} {b.noun} keeps an even line."
    )


def weather_check(o: list[Piece], ctx: Context) -> Check:
    if ctx.temp_high_f is None and ctx.rain_pct < 50:
        return Check(
            "weather", "Weather", None, "No forecast for the day, so the weather wasn’t checked."
        )
    v, _ = weather(tuple(o), ctx)
    temp = ctx.temp_text()
    if v < 0.5:
        rain = ctx.rain_pct >= 50 and any("suede" in p.type or "white sneaker" in p.type for p in o)
        why = (
            "suede or white sneakers in likely rain"
            if rain
            else f"not right for {temp or 'the forecast'}"
        )
        return Check("weather", "Weather", False, f"It’s {why}.")
    return Check("weather", "Weather", True, f"Right for {temp}." if temp else "Fine for the rain.")


def freshness(o: list[Piece], ctx: Context, h: History) -> Check:
    last = h.outfit_last.get(frozenset(p.id for p in o))
    if last is not None and 0 <= (ctx.day - last).days <= REPEAT_OUTFIT_DAYS:
        days = (ctx.day - last).days
        return Check(
            "freshness",
            "Not a repeat",
            False,
            f"You wore this exact outfit {days} day{'s' if days != 1 else ''} ago.",
        )
    for p in o:
        worn = h.piece_last.get(p.id)
        if (
            p.category in ("Tops", "Layers")
            and worn is not None
            and 0 <= (ctx.day - worn).days <= REPEAT_TOP_DAYS
        ):
            days = (ctx.day - worn).days
            when = "today" if days == 0 else ("yesterday" if days == 1 else f"{days} days ago")
            return Check(
                "freshness", "Not a repeat", False, f"You wore the {p.name.lower()} {when}."
            )
    return Check(
        "freshness", "Not a repeat", True, "Nothing on show was worn in the last few days."
    )


@dataclass
class Rating:
    verdict: str  # strong | works | rethink
    headline: str
    checks: list[Check]

    def to_json(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "headline": self.headline,
            "checks": [asdict(c) for c in self.checks],
        }


def rate(o: list[Piece], ctx: Context, h: History, analysis: dict[str, Any] | None) -> Rating:
    checks = [
        structure(o),
        colors(o),
        near_face(o, analysis),
        formality(o, ctx.occasion),
        fit(o, ctx.occasion),
        weather_check(o, ctx),
        freshness(o, ctx, h),
    ]
    return verdict_for(checks, MINOR)


def verdict_for(checks: list[Check], minor: frozenset[str]) -> Rating:
    """Strong when every check with data passes; works when only minor ones miss; else rethink."""
    fails = [c for c in checks if c.ok is False]
    unchecked = [c for c in checks if c.ok is None]
    if any(c.key not in minor for c in fails):
        core = next(c for c in fails if c.key not in minor)
        verdict, headline = "rethink", f"Rethink it: {core.detail[0].lower()}{core.detail[1:]}"
    elif fails:
        verdict, headline = (
            "works",
            f"It works, with one thing to know: {fails[0].detail[0].lower()}{fails[0].detail[1:]}",
        )
    else:
        verdict = "strong"
        headline = "Strong: it passes every check." + (
            f" {len(unchecked)} check{'s' if len(unchecked) != 1 else ''} couldn’t run (see below)."
            if unchecked
            else ""
        )
    return Rating(verdict, headline, checks)

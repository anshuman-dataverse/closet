"""Candidate outfits (SPEC 5.4 steps 1–2)."""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from dataclasses import replace

from .model import Context, Piece

FORMALITY_RANGE = {"office": (3, 5), "college": (2, 4), "party": (2, 5), "home": (1, 3)}
FORMALITY_TARGET = {"office": 4.0, "college": 2.8, "party": 3.5, "home": 1.5}
MAX_CANDIDATES = 5000
UP_WORDS = ("meeting", "presentation", "interview")
DOWN_WORDS = ("gym", "lazy", "home")


def eligible(p: Piece, occasion: str) -> bool:
    if p.status != "active":
        return False
    lo, hi = FORMALITY_RANGE.get(occasion, (1, 5))
    return occasion in p.occasions or (p.formality is not None and lo <= p.formality <= hi)


def needs_layer(ctx: Context) -> bool:
    return (ctx.temp_high_f is not None and ctx.temp_high_f < 60) or ctx.rain_pct >= 50


def apply_note(ctx: Context) -> tuple[Context, int]:
    """Keyword rules: returns the adjusted weather and a formality shift (SPEC 5.4 note rules)."""
    n = ctx.note.lower()
    shift = (1 if any(w in n for w in UP_WORDS) else 0) - (
        1 if any(w in n for w in DOWN_WORDS) else 0
    )
    if "snow" in n:
        high = ctx.temp_high_f if ctx.temp_high_f is not None else 32.0
        ctx = replace(ctx, rain_pct=max(ctx.rain_pct, 80.0), temp_high_f=min(high, 32.0))
    elif "rain" in n:
        ctx = replace(ctx, rain_pct=max(ctx.rain_pct, 80.0))
    return ctx, shift


Outfit = tuple[Piece, ...]


def _slots(pieces: Iterable[Piece], ctx: Context) -> dict[str, list[Piece]]:
    s: dict[str, list[Piece]] = {
        "Tops": [],
        "Bottoms": [],
        "Sets & suits": [],
        "Shoes": [],
        "Layers": [],
    }
    for p in pieces:
        if eligible(p, ctx.occasion) and p.category in s:
            s[p.category].append(p)
    return s


def _combos(
    bases: Sequence[tuple[Piece, ...]],
    shoes: Sequence[Piece | None],
    layers: Sequence[Piece | None],
    limit: int,
    seed: int,
) -> list[Outfit]:
    total = len(bases) * len(shoes) * len(layers)
    if total == 0:
        return []
    idx: Iterable[int] = (
        range(total) if total <= limit else sorted(random.Random(seed).sample(range(total), limit))
    )
    out: list[Outfit] = []
    for k in idx:
        b, rest = divmod(k, len(shoes) * len(layers))
        s, la = divmod(rest, len(layers))
        out.append(tuple(x for x in (*bases[b], layers[la], shoes[s]) if x is not None))
    return out


def candidates(
    pieces: Iterable[Piece], ctx: Context, limit: int = MAX_CANDIDATES, seed: int = 0
) -> list[Outfit]:
    """Top + bottom, or a set; plus shoes if any are eligible; plus a layer when cold or rainy."""
    s = _slots(pieces, ctx)
    bases = [(t, b) for t in s["Tops"] for b in s["Bottoms"]] + [(x,) for x in s["Sets & suits"]]
    shoes: list[Piece | None] = list(s["Shoes"]) or [None]
    layers: list[Piece | None] = list(s["Layers"]) if needs_layer(ctx) and s["Layers"] else [None]
    return _combos(bases, shoes, layers, limit, seed)


def candidates_with(
    new: Piece, pieces: Iterable[Piece], ctx: Context, limit: int = MAX_CANDIDATES
) -> list[Outfit]:
    """Only the candidates that include `new` (for unlock counts), with `new` fixed in its slot.

    A new layer is always included, since unlocks are judged across weather, not for one day.
    Accessories have no slot, so they unlock nothing.
    """
    s = _slots([p for p in pieces if p.id != new.id], ctx)
    cat = new.category
    if cat == "Tops":
        bases: list[tuple[Piece, ...]] = [(new, b) for b in s["Bottoms"]]
    elif cat == "Bottoms":
        bases = [(t, new) for t in s["Tops"]]
    elif cat == "Sets & suits":
        bases = [(new,)]
    elif cat in ("Shoes", "Layers"):
        bases = [(t, b) for t in s["Tops"] for b in s["Bottoms"]] + [
            (x,) for x in s["Sets & suits"]
        ]
    else:
        return []
    shoes: list[Piece | None] = [new] if cat == "Shoes" else (list(s["Shoes"]) or [None])
    if cat == "Layers":
        layers: list[Piece | None] = [new]
    else:
        layers = list(s["Layers"]) if needs_layer(ctx) and s["Layers"] else [None]
    return _combos(bases, shoes, layers, limit, seed=0)

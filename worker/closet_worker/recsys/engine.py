"""Shared recommender steps used by suggest_outfits, check_wish and find_gaps."""

from __future__ import annotations

from typing import Any

from .candidates import Outfit, apply_note, candidates, candidates_with
from .model import Context, History, Piece
from .scoring import Score, score, weights
from .select import pick_diverse

CATEGORY_ORDER = ("Tops", "Sets & suits", "Layers", "Bottoms", "Shoes", "Accessories")


def ordered(o: Outfit) -> Outfit:
    return tuple(
        sorted(
            o, key=lambda p: CATEGORY_ORDER.index(p.category) if p.category in CATEGORY_ORDER else 9
        )
    )


def ideas(
    pieces: list[Piece], ctx: Context, h: History, k: int = 3, profile: dict[str, Any] | None = None
) -> list[tuple[Outfit, Score]]:
    ctx2, shift = apply_note(ctx)
    ranked = [(o, score(o, ctx2, h, shift, profile)) for o in candidates(pieces, ctx2)]
    ranked.sort(key=lambda x: x[1].total, reverse=True)
    return [(ordered(o), s) for o, s in pick_diverse(ranked, k)]


def good_outfits_with(
    new: Piece, pieces: list[Piece], ctx: Context, profile: dict[str, Any] | None = None
) -> list[Outfit]:
    """Outfits that include `new` and score at or above the good threshold (for unlocks).

    Unlocks ask "could this make good outfits?", so recent wear doesn't count: no history.
    """
    thr = weights()["good_threshold"]
    fresh = History()
    return [
        o
        for o in candidates_with(new, pieces, ctx)
        if score(o, ctx, fresh, 0, profile).total >= thr
    ]


def verdict(has_worn_duplicate: bool, has_duplicate: bool, unlocks: int, over_budget: bool) -> str:
    """SPEC 5.6: skip a worn duplicate or over budget; buy when new, useful (3+) and affordable."""
    if has_worn_duplicate or over_budget:
        return "skip"
    if not has_duplicate and unlocks >= 3:
        return "buy"
    return "wait"

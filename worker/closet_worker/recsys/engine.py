"""Shared recommender steps used by suggest_outfits, check_wish and find_gaps."""

from __future__ import annotations

from typing import Any

from .candidates import Outfit, apply_note, candidates, candidates_with
from .model import Context, History, Piece
from .scoring import Score, harmony, score, weights
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
    out = []
    for o, s in pick_diverse(ranked, k):
        acc = accessory_for(o, pieces, ctx2, h)
        if acc is not None:
            o = (*o, acc)
            s.reasons.append({"kind": "accessory", "piece": acc.noun})
        out.append((ordered(o), s))
    return out


def _wants(p: Piece, o: Outfit, ctx: Context) -> bool:
    """Accessory rules (added feature): watch, belt, sunglasses or cap, when they make sense."""
    t = f"{p.type} {p.name.lower()}"
    if "watch" in t:
        return ctx.occasion in ("office", "party")
    if "belt" in t:
        return any(
            q.category == "Bottoms" and any(w in q.type for w in ("trousers", "chinos", "jeans"))
            for q in o
        )
    if "sunglass" in t:
        return ctx.code is not None and ctx.code <= 2 and ctx.occasion != "office"
    if "cap" in t:
        return ctx.occasion in ("college", "home")
    return False


def accessory_for(o: Outfit, pieces: list[Piece], ctx: Context, h: History) -> Piece | None:
    """At most one finishing touch; picked by color harmony, then by how long since it was worn."""
    options = [
        p
        for p in pieces
        if p.category == "Accessories" and p.status == "active" and _wants(p, o, ctx)
    ]
    if not options:
        return None

    def rank(p: Piece) -> tuple[float, int]:
        last = h.piece_last.get(p.id)
        return harmony((*o, p))[0], -1 if last is None else -(ctx.day - last).days

    best = max(options, key=rank)
    return best if harmony((*o, best))[0] > -1.0 else None


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

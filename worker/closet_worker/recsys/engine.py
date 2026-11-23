"""Shared recommender steps used by suggest_outfits, check_wish and find_gaps."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .candidates import Outfit, apply_note, candidates, candidates_with
from .model import Context, History, Piece
from .scoring import Score, harmony, score, weights
from .select import pick_diverse

if TYPE_CHECKING:
    from .compat import CompatScorer

CATEGORY_ORDER = ("Tops", "Sets & suits", "Layers", "Bottoms", "Shoes", "Accessories")


def ordered(o: Outfit) -> Outfit:
    return tuple(
        sorted(
            o, key=lambda p: CATEGORY_ORDER.index(p.category) if p.category in CATEGORY_ORDER else 9
        )
    )


def ranked_candidates(
    pieces: list[Piece],
    ctx: Context,
    h: History,
    profile: dict[str, Any] | None = None,
    compat: CompatScorer | None = None,
) -> tuple[Context, list[tuple[Outfit, Score]]]:
    """Every candidate, best first. With an outfit model, its term is scored in one batch."""
    ctx2, shift = apply_note(ctx)
    cands = list(candidates(pieces, ctx2))
    cs: list[float | None] = compat.scores(cands) if compat else [None] * len(cands)
    ranked = [
        (o, score(o, ctx2, h, shift, profile, None if compat is None else (c or 0.0)))
        for o, c in zip(cands, cs, strict=True)
    ]
    ranked.sort(key=lambda x: x[1].total, reverse=True)
    return ctx2, ranked


# The quality bar: an idea is shown only if it passes every check. Checks without data (no
# colors, no fits, no forecast) pass, since nothing can be said about them.
BAR_FAILS = {
    "harmony": "the colors clash",
    "formality": "the pieces don’t suit the occasion",
    "weather": "they don’t suit today’s weather",
    "freshness": "they repeat a top you just wore, or a whole outfit from this week",
    "palette": "the colors are far from your palette",
    "fit": "two loose fits together lose their shape",
}


REPEAT_TOP_DAYS = 2  # a visible top or layer worn this recently
REPEAT_OUTFIT_DAYS = 7  # the exact same outfit


def repeats(o: Outfit, ctx: Context, h: History) -> bool:
    """Wearing the same trousers or shoes two days apart is normal, so only a visible top or
    layer within 2 days, or the exact outfit within 7, counts as a repeat."""
    last = h.outfit_last.get(frozenset(p.id for p in o))
    if last is not None and 0 <= (ctx.day - last).days <= REPEAT_OUTFIT_DAYS:
        return True
    for p in o:
        worn = h.piece_last.get(p.id)
        visible = p.category in ("Tops", "Layers")
        if visible and worn is not None and 0 <= (ctx.day - worn).days <= REPEAT_TOP_DAYS:
            return True
    return False


def failed_checks(
    o: Outfit,
    s: Score,
    profile: dict[str, Any] | None,
    ctx: Context | None = None,
    h: History | None = None,
) -> list[str]:
    t = s.terms
    fails = []
    if t.get("harmony", 0) < 0:
        fails.append("harmony")
    if any(p.formality is not None for p in o) and t.get("formality", 0) < 0.5:
        fails.append("formality")
    if t.get("weather", 0) < 0 or (0 < t.get("weather", 0) < 0.5):
        fails.append("weather")
    if ctx is not None and h is not None and repeats(o, ctx, h):
        fails.append("freshness")
    if profile and profile.get("best") and t.get("palette", 0) < 0.25:
        fails.append("palette")
    if t.get("fit", 0) < 0:
        fails.append("fit")
    return fails


@dataclass
class BarReport:
    candidates: int
    passed: int
    top_fail: str | None  # the check most candidates failed

    @property
    def message(self) -> str | None:
        if self.passed or not self.candidates:
            return None
        why = BAR_FAILS.get(self.top_fail or "", "none passed every check")
        return f"No combination from your closet passes every check today: most often, {why}."


def ideas_with_report(
    pieces: list[Piece],
    ctx: Context,
    h: History,
    k: int = 3,
    profile: dict[str, Any] | None = None,
    compat: CompatScorer | None = None,
) -> tuple[list[tuple[Outfit, Score]], BarReport]:
    ctx2, ranked = ranked_candidates(pieces, ctx, h, profile, compat)
    fails: Counter[str] = Counter()
    passing = []
    for o, s in ranked:
        f = failed_checks(o, s, profile, ctx2, h)
        if f:
            fails.update(f)
        else:
            passing.append((o, s))
    report = BarReport(len(ranked), len(passing), fails.most_common(1)[0][0] if fails else None)
    return _finish(passing, pieces, ctx2, h, k), report


def ideas(
    pieces: list[Piece],
    ctx: Context,
    h: History,
    k: int = 3,
    profile: dict[str, Any] | None = None,
    compat: CompatScorer | None = None,
) -> list[tuple[Outfit, Score]]:
    return ideas_with_report(pieces, ctx, h, k, profile, compat)[0]


def _finish(
    ranked: list[tuple[Outfit, Score]], pieces: list[Piece], ctx2: Context, h: History, k: int
) -> list[tuple[Outfit, Score]]:
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

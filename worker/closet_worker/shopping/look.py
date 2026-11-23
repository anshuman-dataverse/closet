"""Shop a look: plan a whole outfit, hunt each piece, assemble complete sets within budget.

1. Plan. Slots for the occasion (top, layer, bottom, shoes, and a belt with trousers), a staple
   type per slot at the right formality, and colors chosen with the same harmony and palette
   rules as outfit ideas (your best colors near the face, neutrals below).
   "Use what I own" keeps the best owned piece for every slot your closet already covers.
2. Hunt each slot to buy (smaller limits per slot), budget split by each staple's usual price.
3. Assemble. Every combination of the top picks per slot within the total budget is scored on
   the picks' own scores plus color harmony across the set; up to 3 sets that differ.

A set is shown only when every slot is filled. If a slot found nothing, the summary says which,
and the pieces that were found are still listed on their own.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from closet_worker.recsys.candidates import FORMALITY_RANGE, FORMALITY_TARGET, eligible
from closet_worker.recsys.model import Piece
from closet_worker.recsys.scoring import harmony

from .hunt import Hunt, Outcome, Pick, color_in

STAPLES = Path(__file__).resolve().parent.parent / "vocab" / "staples.yaml"
SLOTS = {
    "office": ("Tops", "Layers", "Bottoms", "Shoes", "Accessories"),
    "party": ("Tops", "Layers", "Bottoms", "Shoes"),
    "college": ("Tops", "Layers", "Bottoms", "Shoes"),
    "home": ("Tops", "Bottoms", "Shoes"),
}
SLOT_LABEL = {
    "Tops": "Top",
    "Layers": "Layer",
    "Bottoms": "Bottoms",
    "Shoes": "Shoes",
    "Accessories": "Belt",
}
# Each occasion's standard pieces, in order of preference (common menswear guidance).
PREFERRED: dict[str, dict[str, tuple[str, ...]]] = {
    "office": {
        "Tops": ("oxford shirt", "dress shirt"),
        "Layers": ("blazer", "v-neck sweater"),
        "Bottoms": ("dress trousers", "chinos"),
        "Shoes": ("loafers", "derby shoes"),
        "Accessories": ("belt",),
    },
    "college": {
        "Tops": ("oxford shirt", "henley", "t-shirt"),
        "Layers": ("crew neck sweater", "overshirt"),
        "Bottoms": ("chinos", "dark wash jeans"),
        "Shoes": ("white sneakers", "sneakers"),
    },
    "party": {
        "Tops": ("oxford shirt", "knit polo"),
        "Layers": ("blazer", "bomber jacket"),
        "Bottoms": ("dark wash jeans", "chinos"),
        "Shoes": ("chelsea boots", "loafers"),
    },
    "home": {
        "Tops": ("t-shirt", "henley"),
        "Bottoms": ("joggers", "shorts"),
        "Shoes": ("sneakers", "sandals"),
    },
}
# Types that already name their color: the search uses the type alone.
IMPLIED_COLOR = {
    "dark wash jeans": "indigo",
    "light wash jeans": "light blue",
    "white sneakers": "white",
}
# What a product's name must say to count for a slot (singular forms match plurals too).
NOUNS = {
    "oxford shirt": ("oxford",),
    "dress shirt": ("dress shirt", "shirt"),
    "henley": ("henley",),
    "t-shirt": ("t-shirt", "tee"),
    "knit polo": ("polo",),
    "blazer": ("blazer", "sport coat", "sportcoat"),
    "v-neck sweater": ("sweater",),
    "crew neck sweater": ("sweater",),
    "overshirt": ("overshirt", "shirt jacket", "shacket"),
    "bomber jacket": ("bomber",),
    "dress trousers": ("trouser", "dress pant"),
    "chinos": ("chino",),
    "dark wash jeans": ("jean",),
    "joggers": ("jogger",),
    "shorts": ("short",),
    "loafers": ("loafer",),
    "derby shoes": ("derby",),
    "chelsea boots": ("chelsea",),
    "white sneakers": ("sneaker",),
    "sneakers": ("sneaker",),
    "sandals": ("sandal",),
    "belt": ("belt",),
}
PER_SLOT = 3  # top picks per slot that go into combinations
MAX_SETS = 3


@dataclass(frozen=True)
class Staple:
    category: str
    type: str
    colors: tuple[str, ...]
    formality: int
    price: tuple[int, int]


@cache
def staples() -> tuple[Staple, ...]:
    out = []
    for s in yaml.safe_load(STAPLES.read_text()):
        out.append(
            Staple(
                s["category"],
                s["type"],
                tuple(s["colors"]),
                int(s["formality"]),
                (int(s["price"][0]), int(s["price"][1])),
            )
        )
    return tuple(out)


def staple_for(category: str, occasion: str) -> Staple | None:
    """The staple whose formality is closest to the occasion's target, within its range."""
    lo, hi = FORMALITY_RANGE.get(occasion, (1, 5))
    target = FORMALITY_TARGET.get(occasion, 3.0)
    pool = [s for s in staples() if s.category == category and lo <= s.formality <= hi]
    for t in PREFERRED.get(occasion, {}).get(category, ()):
        hit = next((s for s in staples() if s.category == category and s.type == t), None)
        if hit is not None:
            return hit
    if category == "Accessories":
        pool = [s for s in pool if s.type == "belt"]
    if category == "Layers":  # a wearable layer, not a winter coat, by default
        pool = [
            s
            for s in pool
            if s.type not in ("wool overcoat", "puffer jacket", "rain jacket", "trench coat")
        ]
    return min(pool, key=lambda s: (abs(s.formality - target), s.price[0])) if pool else None


@dataclass
class Slot:
    category: str
    staple: Staple
    color: str
    owned: Piece | None = None  # "use what I own": this slot is already covered

    @property
    def query(self) -> str:
        t = self.staple.type
        return t if t in IMPLIED_COLOR else f"{self.color} {t}"

    @property
    def label(self) -> str:
        return SLOT_LABEL.get(self.category, self.category)


def _colors(st: Staple, analysis: dict[str, Any] | None) -> tuple[str, ...]:
    """Your best colors for tops and layers, your neutrals below the waist (when they suit the
    staple's usual colors), else the staple's own usual colors."""
    if st.type in IMPLIED_COLOR:
        return (IMPLIED_COLOR[st.type],)
    if not analysis or not analysis.get("best"):
        return st.colors
    best = [c["name"].lower() for c in analysis["best"]]
    neutrals = [c["name"].lower() for c in analysis.get("neutrals", [])]
    if st.category == "Tops":
        return tuple(best[:3]) or st.colors
    if st.category == "Layers":  # a neutral layer over a colored shirt
        return tuple(n for n in neutrals if n != "white")[:3] or st.colors
    usual = [c for c in neutrals if c in st.colors]
    return tuple(usual[:2]) or st.colors


def plan(
    occasion: str, analysis: dict[str, Any] | None, owned: list[Piece], mode: str
) -> list[Slot]:
    """The slots and colors whose combination scores best on color harmony."""
    chosen: dict[str, Staple] = {}
    for c in SLOTS.get(occasion, SLOTS["office"]):
        st = staple_for(c, occasion)
        if st is not None:
            chosen[c] = st
    cats = tuple(chosen)
    options = [_colors(chosen[c], analysis) for c in cats]

    def as_pieces(colors: tuple[str, ...]) -> tuple[Piece, ...]:
        return tuple(
            Piece(
                id=f"plan:{c}",
                name=f"{col} {chosen[c].type}",
                category=c,
                type=chosen[c].type,
                color_name=col,
            )
            for c, col in zip(cats, colors, strict=True)
        )

    def ok(cs: tuple[str, ...]) -> bool:
        by = dict(zip(cats, cs, strict=True))
        # A layer in the same color as the shirt under it reads as one block.
        same_top = "Tops" in by and "Layers" in by and by["Tops"] == by["Layers"]
        # A blazer or sweater in exactly the trousers' color looks like a suit that isn't one.
        same_bottom = "Layers" in by and "Bottoms" in by and by["Layers"] == by["Bottoms"]
        return not (same_top or same_bottom)

    combos = [cs for cs in itertools.product(*options) if ok(cs)] or list(
        itertools.product(*options)
    )
    best = max(combos, key=lambda cs: harmony(as_pieces(cs))[0])
    slots = [Slot(c, chosen[c], col) for c, col in zip(cats, best, strict=True)]
    if mode == "own":
        for sl in slots:
            mine = [p for p in owned if p.category == sl.category and eligible(p, occasion)]
            if sl.category == "Accessories":
                mine = [p for p in mine if "belt" in f"{p.type} {p.name.lower()}"]
            if mine:
                others = [x for x in as_pieces(best) if x.category != sl.category]
                sl.owned = max(mine, key=lambda p: harmony((*others, p))[0])
    return slots


def budgets(slots: list[Slot], total_cents: int | None) -> dict[str, int | None]:
    """Each slot to buy gets a share of the total by its staple's usual price, with 60% slack
    (the assembled set still has to fit the total)."""
    buy = [s for s in slots if s.owned is None]
    if total_cents is None or not buy:
        return {s.category: None for s in buy}
    mids = {s.category: sum(s.staple.price) / 2 for s in buy}
    whole = sum(mids.values())
    return {c: round(total_cents * m / whole * 1.6) for c, m in mids.items()}


@dataclass
class LookSet:
    picks: dict[str, Pick]  # category → pick (bought slots only)
    owned: dict[str, Piece]
    total_cents: int
    score: float


@dataclass
class LookOutcome:
    slots: list[Slot]
    found: dict[str, list[Pick]]  # category → picks found (bought slots)
    sets: list[LookSet]
    summary: str
    pages_checked: int
    skipped: dict[str, str] = field(default_factory=dict)


def assemble(
    slots: list[Slot], found: dict[str, list[Pick]], total_cents: int | None
) -> list[LookSet]:
    buy = [s for s in slots if s.owned is None]
    owned = {s.category: s.owned for s in slots if s.owned is not None}
    if any(not found.get(s.category) for s in buy):
        return []
    pools = [found[s.category][:PER_SLOT] for s in buy]
    sets: list[LookSet] = []
    for combo in itertools.product(*pools) if buy else [()]:
        total = sum(p.listing.price_cents or 0 for p in combo)
        if total_cents is not None and total > total_cents:
            continue
        pieces = [
            Piece(
                id=p.listing.url,
                name=p.listing.title,
                category=s.category,
                type=s.staple.type,
                color_name=color_in(p.listing.title) or s.color,
            )
            for s, p in zip(buy, combo, strict=True)
        ] + list(owned.values())
        h = harmony(tuple(pieces))[0]
        if h < 0:
            continue  # the set's colors clash: not shown
        score = (sum(p.score for p in combo) / len(combo) if combo else 0.0) + 0.5 * h
        sets.append(
            LookSet({s.category: p for s, p in zip(buy, combo, strict=True)}, owned, total, score)
        )
    sets.sort(key=lambda x: -x.score)
    chosen: list[LookSet] = []
    for ls in sets:  # sets that differ: at most one bought piece in common with an earlier set
        urls = {p.listing.url for p in ls.picks.values()}
        if all(len(urls & {p.listing.url for p in c.picks.values()}) <= 1 for c in chosen):
            chosen.append(ls)
        if len(chosen) == MAX_SETS:
            break
    return chosen


def summarize(
    slots: list[Slot], found: dict[str, list[Pick]], sets: list[LookSet], total_cents: int | None
) -> str:
    buy = [s for s in slots if s.owned is None]
    missing = [s.label.lower() for s in buy if not found.get(s.category)]
    own = [s for s in slots if s.owned is not None]
    out = []
    if sets:
        cap = "" if total_cents is None else f" within ${total_cents / 100:,.0f}"
        out.append(f"{len(sets)} complete look{'s' if len(sets) != 1 else ''}{cap}.")
    elif missing:
        out.append(
            f"No complete look: no {', '.join(missing)} in budget at stores that allow reading."
        )
    else:
        cheapest = sum(min(p.listing.price_cents or 0 for p in found[s.category]) for s in buy)
        if total_cents is not None and cheapest > total_cents:
            out.append(
                f"No complete look within ${total_cents / 100:,.0f}: the cheapest set found "
                f"comes to ${cheapest / 100:,.2f}. Raise the budget a little, or use what you own."
            )
        else:
            out.append(
                "The pieces found don’t go together in color within the budget: "
                "try a higher budget."
            )
    if own:
        out.append(f"Using from your closet: {', '.join(s.owned.name for s in own if s.owned)}.")
    if not buy:
        out.append("Your closet already covers every piece of this look.")
    return " ".join(out)


Hunter = Callable[[Hunt], Outcome]


def shop_look(
    h: Hunt, mode: str, analysis: dict[str, Any] | None, owned: list[Piece], hunt: Hunter
) -> LookOutcome:
    slots = plan(h.occasion or "office", analysis, owned, mode)
    caps = budgets(slots, h.budget_max_cents)
    found: dict[str, list[Pick]] = {}
    pages = 0
    skipped: dict[str, str] = {}
    for s in slots:
        if s.owned is not None:
            continue
        sub = Hunt(
            s.query,
            None,
            caps.get(s.category),
            h.occasion,
            h.wears,
            h.favorites,
            h.best_colors,
            must_have=NOUNS.get(s.staple.type, (s.staple.type.split()[-1],)),
            color=None if s.staple.type in IMPLIED_COLOR else s.color,
        )
        out = hunt(sub)
        found[s.category] = out.picks
        pages += out.pages_checked
        skipped.update(out.skipped)
    sets = assemble(slots, found, h.budget_max_cents)
    return LookOutcome(
        slots, found, sets, summarize(slots, found, sets, h.budget_max_cents), pages, skipped
    )

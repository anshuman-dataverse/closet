"""`find_gaps` (SPEC 5.7): staple ideas that unlock the most new outfits for an occasion."""

from __future__ import annotations

from collections import Counter
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from closet_worker.recsys.candidates import eligible
from closet_worker.recsys.engine import good_outfits_with
from closet_worker.recsys.model import Context, History, Piece

from .context import JobContext
from .tag_item import BadJob

PER_CATEGORY = 2
TOP_N = 5
PLURAL = {
    "shirt": "shirts",
    "chinos": "chinos",
    "jeans": "jeans",
    "trousers": "trousers",
    "shoes": "shoes",
}


@cache
def staples() -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = yaml.safe_load(
        (Path(__file__).resolve().parent.parent / "vocab" / "staples.yaml").read_text()
    )
    return data


def _word(n: int) -> str:
    return "outfit" if n == 1 else "outfits"


def _plural(noun: str) -> str:
    return PLURAL.get(noun, noun if noun.endswith("s") else noun + "s")


def _owned(p: Piece, owned: list[Piece]) -> bool:
    """Text-only near-duplicate: same category, same color, and the type's last word in common."""
    return any(
        o.category == p.category
        and o.color_name == p.color_name
        and p.noun in f"{o.type} {o.name.lower()}"
        for o in owned
        if o.status != "retired"
    )


def gap_ideas(pieces: list[Piece], ctx: Context, h: History) -> list[dict[str, Any]]:
    scored = []
    for s in staples():
        for color in s["colors"]:
            p = Piece(
                id=f"staple:{s['type']}:{color}",
                name=f"{color.capitalize()} {s['type']}",
                category=s["category"],
                type=s["type"],
                color_name=color,
                formality=int(s["formality"]),
                warmth=s["warmth"],
            )
            if not eligible(p, ctx.occasion) or _owned(p, pieces):
                continue
            good = good_outfits_with(p, pieces, ctx)
            if good:
                nouns = Counter(
                    q.noun for o in good for q in o if q.id != p.id and q.category != "Shoes"
                )
                scored.append((len(good), p, s, [n for n, _ in nouns.most_common(2)]))
    scored.sort(key=lambda x: -x[0])
    out: list[dict[str, Any]] = []
    per_cat: Counter[str] = Counter()
    seen_types: set[str] = set()
    for n, p, s, partners in scored:
        if per_cat[p.category] >= PER_CATEGORY or p.type in seen_types:
            continue
        per_cat[p.category] += 1
        seen_types.add(p.type)
        with_ = " and ".join(_plural(x) for x in partners) if partners else "what you own"
        out.append(
            {
                "name": p.name,
                "type": p.type,
                "category": p.category,
                "color_name": p.color_name,
                "price_min_cents": int(s["price"][0]) * 100,
                "price_max_cents": int(s["price"][1]) * 100,
                "unlocks": n,
                "reason": f"Adds {n} new {ctx.occasion} {_word(n)} with your {with_}.",
            }
        )
        if len(out) == TOP_N:
            break
    return out


def run(payload: dict[str, Any], ctx: JobContext | None) -> dict[str, Any]:
    if ctx is None or ctx.items is None:
        raise BadJob("no item store")
    c = Context(
        occasion=str(payload.get("occasion") or "office"),
        day=date.fromisoformat(str(payload.get("date") or date.today().isoformat())),
    )
    pieces = [Piece.from_row(r) for r in ctx.items.list_items()]
    h = History.from_logs(ctx.items.list_wear_logs())
    return {"occasion": c.occasion, "ideas": gap_ideas(pieces, c, h)}

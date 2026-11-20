"""Reason templates (SPEC 5.10): several phrasings per reason, never adding facts."""

from __future__ import annotations

import random
from typing import Any

PAIR = (
    "{A} and {b} is a classic pairing",
    "{A} and {b} sit well together",
    "{A} with {b} keeps it easy",
)
FRESH = (
    "you haven’t worn the {piece} in {days} days",
    "the {piece} hasn’t been out in {days} days",
    "it’s been {days} days since the {piece}",
)
NEW = ("none of these pieces has been worn yet", "it’s a first outing for all of these")
WEATHER = (
    "The {piece} handles {temp}.",
    "The {piece} covers {temp}.",
    "Bring the {piece} for {temp}.",
)
RAIN = ("Nothing here minds the rain.", "Rain-safe shoes and all.")
FORMAL = ("Sharp enough for the meeting.", "Dressed up a notch for today.")


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def render(reasons: list[dict[str, Any]], seed: int = 0) -> str:
    """Up to two clauses joined into one sentence, plus a short weather or formality line."""
    rng = random.Random(seed)
    clauses: list[str] = []
    extra: list[str] = []
    for r in reasons:
        k = r.get("kind")
        if k == "pair" and len(clauses) < 2:
            clauses.append(rng.choice(PAIR).format(A=_cap(str(r["a"])), b=str(r["b"])))
        elif k == "fresh" and len(clauses) < 2:
            clauses.append(rng.choice(FRESH).format(piece=r["piece"], days=r["days"]))
        elif k == "new" and len(clauses) < 2:
            clauses.append(rng.choice(NEW))
        elif k == "weather" and r.get("temp") and not extra:
            extra.append(rng.choice(WEATHER).format(piece=r["piece"], temp=r["temp"]))
        elif k == "rain" and not extra:
            extra.append(rng.choice(RAIN))
        elif k == "formal_up" and not extra:
            extra.append(rng.choice(FORMAL))
    if not clauses and not extra:
        return "A fresh mix from your closet."
    first = _cap(", and ".join(clauses)) + "." if clauses else ""
    return " ".join(x for x in (first, *extra) if x)


def _n(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


VERDICT_WORD = {"buy": "Worth it", "wait": "Wait on it", "skip": "Skip it"}


def wish_reasons(
    dupes: list[dict[str, Any]],
    unlocks: int,
    occasion: str | None,
    over_by_cents: int,
    budget_cents: int,
) -> list[str]:
    out: list[str] = []
    if dupes:
        worn = [d for d in dupes if d.get("wears", 0) > 0]
        names = ", ".join(str(d["name"]) for d in dupes[:3])
        if len(dupes) == 1:
            out.append(f"You own something very similar: {names}.")
        else:
            out.append(f"You own {len(dupes)} very similar pieces: {names}.")
        if worn:
            w = max(worn, key=lambda d: d.get("wears", 0))
            out.append(
                f"You’ve worn the {w['name']} {w['wears']} {_n(w['wears'], 'time', 'times')}."
            )
    where = f" {occasion}" if occasion else ""
    if unlocks:
        out.append(
            f"It adds {unlocks} new{where} {_n(unlocks, 'outfit', 'outfits')} with what you own."
        )
    else:
        out.append(f"It doesn’t make any new{where} outfits with what you own yet.")
    if over_by_cents > 0:
        out.append(
            f"It puts you ${over_by_cents / 100:,.0f} over your "
            f"${budget_cents / 100:,.0f} budget this month."
        )
    return out

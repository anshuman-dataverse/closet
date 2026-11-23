"""Would it suit me? One piece you're thinking of buying (a product link or a screenshot), checked
against you and your closet. Each check says why; checks without data say what would let them run.

- Near your face (tops, layers, sets): its color against your palette, as in Check my outfit.
  Light colors read from a picture aren't trusted (screens and photos wash them out).
- Formality: right for the occasion you picked (or which occasions it suits).
- Goes with your closet: how many good outfits it makes with what you own.
- Already own it: a very similar piece you own (worn: core; never worn: minor).
- Fit: the fit the page states against your preferred fit (minor; never guessed from a picture).

The verdict is words (strong / works / rethink), never a percentage. It can't show the piece on
your body: that would need try-on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from closet_worker.recsys.candidates import FORMALITY_RANGE, FORMALITY_TARGET
from closet_worker.recsys.model import Piece
from closet_worker.recsys.rate import OCCASION_WORD, Check, Rating, near_face, verdict_for

FACE = frozenset({"Tops", "Layers", "Sets & suits"})
LIGHT = frozenset(
    {"white", "off-white", "ivory", "cream", "light grey", "silver", "beige", "stone"}
)
FIT_WORDS = {
    "slim": ("slim", "skinny", "tailored", "fitted"),
    "regular": ("regular fit", "classic fit", "straight fit", "standard fit"),
    "relaxed": ("relaxed", "loose", "easy fit", "oversized", "boxy", "baggy"),
}
MINOR = frozenset({"fit", "similar"})
ORDER = ("office", "college", "party", "home")


@dataclass
class Candidate:
    piece: Piece
    color_source: str  # store | picture | you
    title: str = ""  # the product's name (for the stated fit)
    duplicates: list[dict[str, Any]] | None = field(default_factory=list)  # None: not compared
    unlocks: dict[str, int] = field(default_factory=dict)  # occasion → good outfits


def stated_fit(title: str) -> str | None:
    t = f" {title.lower()} "
    for fit, words in FIT_WORDS.items():
        if any(w in t for w in words):
            return fit
    return None


def palette_check(c: Candidate, analysis: dict[str, Any] | None) -> Check | None:
    p = c.piece
    if p.category not in FACE:
        return None  # worn away from the face: your palette doesn't decide it
    if c.color_source == "picture" and p.color_name in LIGHT:
        return Check(
            "palette",
            "Near your face",
            None,
            f"It looks {p.color_name}, but light colors can’t be read reliably from a picture. "
            "Set the color to check it against your palette.",
        )
    out = near_face([p], analysis)
    if c.color_source == "picture" and out.ok is not None:
        out.detail += " (Color read from the picture.)"
    return out


def formality_check(c: Candidate, occasion: str | None) -> Check:
    f = c.piece.formality
    if f is None:
        return Check(
            "formality", "Formality", None, "Its type isn’t known, so formality wasn’t checked."
        )
    if occasion:
        lo, hi = FORMALITY_RANGE.get(occasion, (1, 5))
        where = OCCASION_WORD.get(occasion, occasion)
        if f < lo:
            return Check("formality", "Formality", False, f"It’s too casual for {where}.")
        if f > hi:
            return Check("formality", "Formality", False, f"It’s too dressed up for {where}.")
        return Check("formality", "Formality", True, f"The right formality for {where}.")
    fits = [o for o in ORDER if FORMALITY_RANGE[o][0] <= f <= FORMALITY_RANGE[o][1]]
    best = min(ORDER, key=lambda o: abs(FORMALITY_TARGET[o] - f))
    words = [OCCASION_WORD[o] for o in fits] or [OCCASION_WORD[best]]
    joined = words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
    return Check("formality", "Formality", True, f"Its formality suits {joined}.")


def closet_check(c: Candidate, occasion: str | None) -> Check:
    if not c.unlocks:
        return Check(
            "closet", "Goes with your closet", None, "Add pieces to your closet to check this."
        )
    n = sum(c.unlocks.values())
    where = f" for {OCCASION_WORD.get(occasion, occasion)}" if occasion else ""
    if n == 0:
        return Check(
            "closet",
            "Goes with your closet",
            False,
            f"Nothing you own makes a complete, good outfit with it{where} yet.",
        )
    return Check(
        "closet",
        "Goes with your closet",
        True,
        f"It makes {n} good outfit{'s' if n != 1 else ''} with what you own{where}.",
    )


def duplicate_check(c: Candidate) -> Check:
    if c.duplicates is None:
        return Check("duplicate", "Already own it", None, "Your closet wasn’t compared this time.")
    worn = [d for d in c.duplicates if d.get("wears", 0) > 0]
    if worn:
        return Check(
            "duplicate",
            "Already own it",
            False,
            f"You already own the {worn[0]['name'].lower()} and wear it.",
        )
    if c.duplicates:
        return Check(
            "similar",
            "Already own it",
            False,
            f"You own the similar {c.duplicates[0]['name'].lower()}, "
            "though you haven’t worn it yet.",
        )
    return Check("duplicate", "Already own it", True, "Nothing in your closet is very similar.")


def fit_check(c: Candidate, fit_pref: str | None) -> Check:
    if not fit_pref:
        return Check("fit", "Fit", None, "Set your preferred fit in Settings to check it.")
    got = stated_fit(c.title)
    if got is None:
        return Check("fit", "Fit", None, "The page doesn’t say how it’s cut.")
    if got == fit_pref:
        return Check("fit", "Fit", True, f"It’s cut {got}, your preferred fit.")
    return Check("fit", "Fit", False, f"It’s cut {got}; you prefer {fit_pref}.")


def judge(
    c: Candidate, occasion: str | None, analysis: dict[str, Any] | None, fit_pref: str | None
) -> Rating:
    checks = [
        x
        for x in (
            palette_check(c, analysis),
            formality_check(c, occasion),
            closet_check(c, occasion),
            duplicate_check(c),
            fit_check(c, fit_pref),
        )
        if x is not None
    ]
    return verdict_for(checks, MINOR)

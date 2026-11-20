"""Pick 3 with diversity (SPEC 5.4 step 5): each pick shares ≤1 piece with each earlier pick."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

from .candidates import Outfit

T = TypeVar("T")


def pick_diverse[T](
    ranked: Sequence[tuple[Outfit, T]], k: int = 3, max_shared: int = 1
) -> list[tuple[Outfit, T]]:
    chosen: list[tuple[Outfit, T]] = []
    for o, meta in ranked:
        ids = {p.id for p in o}
        if all(len(ids & {p.id for p in c}) <= max_shared for c, _ in chosen):
            chosen.append((o, meta))
            if len(chosen) == k:
                break
    return chosen

from __future__ import annotations

from datetime import date
from typing import Any

from closet_worker.recsys.model import Context, Piece

TODAY = date(2026, 11, 20)


def piece(id: str, category: str, **kw: Any) -> Piece:
    base: dict[str, Any] = {
        "name": id,
        "formality": 3,
        "warmth": "medium",
        "occasions": ("office",),
    }
    base.update(kw)
    return Piece(id=id, category=category, **base)


def closet() -> list[Piece]:
    return [
        piece("navy-oxford", "Tops", type="oxford shirt", color_name="navy", warmth="light"),
        piece("white-oxford", "Tops", type="oxford shirt", color_name="white", warmth="light"),
        piece("grey-chinos", "Bottoms", type="chinos", color_name="grey"),
        piece("khaki-chinos", "Bottoms", type="chinos", color_name="khaki"),
        piece(
            "charcoal-sweater",
            "Layers",
            type="crew neck sweater",
            color_name="charcoal",
            warmth="warm",
        ),
        piece("brown-boots", "Shoes", type="chelsea boots", color_name="brown"),
        piece("white-sneakers", "Shoes", type="white sneakers", color_name="white", formality=2),
        piece(
            "hoodie", "Layers", type="hoodie", color_name="grey", formality=1, occasions=("home",)
        ),
        piece(
            "joggers",
            "Bottoms",
            type="joggers",
            color_name="grey",
            formality=1,
            occasions=("home",),
        ),
        piece("retired-tee", "Tops", type="t-shirt", color_name="red", status="retired"),
        piece("laundry-shirt", "Tops", type="dress shirt", color_name="white", status="laundry"),
    ]


def ctx(**kw: Any) -> Context:
    base: dict[str, Any] = {"occasion": "office", "day": TODAY}
    base.update(kw)
    return Context(**base)

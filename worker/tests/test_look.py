"""Shop a look (shopping/look.py) and the stricter listing filters, offline."""

from __future__ import annotations

import itertools
from typing import Any

from closet_worker.recsys.model import Piece
from closet_worker.shopping import hunt as H
from closet_worker.shopping import look as L
from closet_worker.shopping.parse import Listing

PROFILE = {
    "best": [
        {"name": "Light blue", "hex": "#9ec5e6"},
        {"name": "Mint", "hex": "#a8e6cf"},
        {"name": "Navy", "hex": "#1f2a48"},
    ],
    "neutrals": [
        {"name": "Charcoal", "hex": "#36454f"},
        {"name": "Navy", "hex": "#1f2a48"},
        {"name": "Grey", "hex": "#8e8e8e"},
        {"name": "White", "hex": "#ffffff"},
    ],
}


def test_plans_a_sensible_office_look() -> None:
    slots = L.plan("office", PROFILE, [], "new")
    q = {s.label: s.query for s in slots}
    assert q == {
        "Top": "light blue oxford shirt",
        "Layer": "charcoal blazer",
        "Bottoms": "navy dress trousers",
        "Shoes": "brown loafers",
        "Belt": "brown belt",
    }
    by = {s.category: s.color for s in slots}
    assert by["Layers"] not in (by["Tops"], by["Bottoms"])  # no single block, no fake suit


def test_types_that_name_their_color() -> None:
    q = {s.label: s.query for s in L.plan("college", PROFILE, [], "new")}
    assert q["Shoes"] == "white sneakers"
    assert {s.label: s.query for s in L.plan("party", PROFILE, [], "new")}[
        "Bottoms"
    ] == "dark wash jeans"


def test_use_what_i_own_keeps_covered_slots() -> None:
    owned = [
        Piece(
            id="c",
            name="Navy chinos",
            category="Bottoms",
            type="chinos",
            color_name="navy",
            formality=3,
            occasions=("college",),
        ),
        Piece(
            id="s",
            name="White sneakers",
            category="Shoes",
            type="white sneakers",
            color_name="white",
            formality=2,
            occasions=("college",),
        ),
    ]
    slots = L.plan("college", PROFILE, owned, "own")
    assert {s.label: (s.owned.id if s.owned else None) for s in slots} == {
        "Top": None,
        "Layer": None,
        "Bottoms": "c",
        "Shoes": "s",
    }
    assert set(L.budgets(slots, 20000)) == {"Tops", "Layers"}


def pick(cat: str, title: str, price: int, score: float = 0.5, url: str | None = None) -> H.Pick:
    it = Listing(url or f"https://x/{title}", title, price, "USD", True)
    return H.Pick(
        it, "Gap", score, {"match": 1, "palette": 0, "discount": 0, "rating": 0, "favorite": 0}
    )


def test_assemble_respects_budget_and_varies_sets() -> None:
    slots = [s for s in L.plan("home", PROFILE, [], "new")]
    found = {
        "Tops": [
            pick("Tops", "Light blue tee", 2000, 0.9),
            pick("Tops", "Light blue tee 2", 1500, 0.6),
        ],
        "Bottoms": [
            pick("Bottoms", "Navy joggers", 4000, 0.8),
            pick("Bottoms", "Navy joggers 2", 3000, 0.7),
        ],
        "Shoes": [
            pick("Shoes", "Grey sneakers", 6000, 0.9),
            pick("Shoes", "Grey sneakers 2", 9000, 0.9),
        ],
    }
    sets = L.assemble(slots, found, 12000)
    assert sets and all(s.total_cents <= 12000 for s in sets)
    for a, b in itertools.pairwise(sets):
        assert (
            len(
                {p.listing.url for p in a.picks.values()}
                & {p.listing.url for p in b.picks.values()}
            )
            <= 1
        )
    assert L.summarize(slots, found, sets, 12000).startswith(f"{len(sets)} complete look")


def test_missing_slot_and_over_budget_are_explained() -> None:
    slots = L.plan("home", PROFILE, [], "new")
    found: dict[str, Any] = {
        "Tops": [pick("Tops", "Tee", 2000)],
        "Bottoms": [],
        "Shoes": [pick("Shoes", "Sneaker", 5000)],
    }
    assert L.assemble(slots, found, 50000) == []
    assert (
        L.summarize(slots, found, [], 50000)
        == "No complete look: no bottoms in budget at stores that allow reading."
    )
    found["Bottoms"] = [pick("Bottoms", "Joggers", 4000)]
    msg = L.summarize(slots, found, L.assemble(slots, found, 10000), 10000)
    assert "cheapest set found comes to $110.00" in msg


def listing(title: str, **kw: Any) -> Listing:
    return Listing("https://x/p", title, 3000, "USD", True, **kw)


def test_wears_filter_uses_page_data_name_and_breadcrumbs() -> None:
    assert not H.for_wears(listing("Women's Brooklin Loafers"), "menswear")
    assert not H.for_wears(listing("365 Pleated Trousers", gender="female"), "menswear")
    assert H.for_wears(listing("Men's Ragg Wool Sweater"), "menswear")
    assert not H.for_wears(listing("Men's Ragg Wool Sweater"), "womenswear")
    assert H.for_wears(listing("Women's tee"), "womenswear")  # "women" isn't read as "men"
    assert H.for_wears(listing("Anything"), None)


def test_slot_match_needs_the_item_and_the_stated_color() -> None:
    h = H.Hunt("navy chinos", None, None, must_have=("chino",), color="navy")
    assert H.matches_slot(listing("Straight Stretch Chino", color="Navy Blue"), h)
    assert not H.matches_slot(listing("Straight Stretch Chino"), h)  # color not stated: not assumed
    assert not H.matches_slot(listing("Pleated Trousers", color="Navy"), h)  # not a chino
    assert not H.matches_slot(listing("Stretch Chino", color="Navy Blue Stripe"), h)  # a pattern
    assert not H.matches_slot(listing("Stretch Chino | Khaki"), h)  # another color


def test_kids_sections_are_dropped() -> None:
    h = H.Hunt("white sneakers", None, None)
    assert not H.keep(listing("Baby Brannan Bear Logo Sneaker"), h)
    assert not H.keep(listing("Canvas Sneaker", crumbs=["Kids", "Shoes"]), h)
    assert H.keep(listing("Canvas Sneaker", crumbs=["Men", "Shoes"]), h)

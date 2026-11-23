"""Would it suit me? (recsys/suits.py and jobs/suits_me.py), offline."""

from __future__ import annotations

import json
import socket
from typing import Any

import pytest

from closet_worker.jobs import suits_me
from closet_worker.jobs.context import JobContext
from closet_worker.jobs.tag_item import BadJob
from closet_worker.recsys.model import Piece
from closet_worker.recsys.suits import Candidate, judge, stated_fit
from closet_worker.shopping.fetch import Fetcher, Page

from .test_recsys_jobs import Store, jctx, store  # noqa: F401 (fixtures)
from .test_tag_item import vision

PROFILE = {
    "best": [{"name": "Navy", "hex": "#1f2a48"}, {"name": "Teal", "hex": "#008080"}],
    "neutrals": [{"name": "Grey", "hex": "#8e8e8e"}],
    "careful": [{"name": "Orange", "hex": "#ff8c00"}],
}


def piece(**kw: Any) -> Piece:
    base: dict[str, Any] = {
        "id": "check",
        "name": "Knit polo",
        "category": "Tops",
        "type": "knit polo",
        "color_name": "navy",
        "formality": 3,
    }
    base.update(kw)
    return Piece(**base)


def by_key(r: Any) -> dict[str, Any]:
    return {c.key: c for c in r.checks}


def test_a_good_piece_is_strong_and_says_why() -> None:
    c = Candidate(piece(), "store", "Slim knit polo", [], {"office": 3})
    r = judge(c, "office", PROFILE, "slim")
    assert r.verdict == "strong"
    k = by_key(r)
    assert k["palette"].ok and "navy" in k["palette"].detail
    assert (
        k["formality"].ok
        and k["closet"].detail == "It makes 3 good outfits with what you own for the office."
    )
    assert k["duplicate"].ok and k["fit"].detail == "It’s cut slim, your preferred fit."


def test_careful_color_near_the_face_is_rethink() -> None:
    c = Candidate(piece(color_name="orange"), "store", "", [], {"college": 2})
    r = judge(c, "college", PROFILE, None)
    assert r.verdict == "rethink" and "use carefully" in r.headline


def test_worn_duplicate_and_no_outfits_are_core_unworn_lookalike_is_minor() -> None:
    worn = Candidate(piece(), "store", "", [{"name": "Navy polo", "wears": 4}], {"office": 2})
    assert judge(worn, "office", PROFILE, None).verdict == "rethink"
    unworn = Candidate(piece(), "store", "", [{"name": "Navy polo", "wears": 0}], {"office": 2})
    assert judge(unworn, "office", PROFILE, None).verdict == "works"
    lonely = Candidate(piece(), "store", "", [], {"office": 0})
    r = judge(lonely, "office", PROFILE, None)
    assert r.verdict == "rethink" and "nothing you own" in r.headline


def test_too_casual_for_the_office() -> None:
    c = Candidate(piece(type="t-shirt", formality=1), "store", "", [], {"office": 1})
    assert by_key(judge(c, "office", PROFILE, None))["formality"].detail == (
        "It’s too casual for the office."
    )


def test_light_colors_from_a_picture_arent_trusted_and_bottoms_skip_the_palette() -> None:
    c = Candidate(piece(color_name="white"), "picture", "", [], {"office": 2})
    k = by_key(judge(c, "office", PROFILE, None))
    assert k["palette"].ok is None and "can’t be read reliably" in k["palette"].detail
    dark = Candidate(piece(color_name="teal", color_hex="#008080"), "picture", "", [], {"party": 1})
    assert (
        "(Color read from the picture.)"
        in by_key(judge(dark, "party", PROFILE, None))["palette"].detail
    )
    chinos = Candidate(piece(category="Bottoms", type="chinos"), "store", "", [], {"office": 1})
    assert "palette" not in by_key(judge(chinos, "office", PROFILE, None))


def test_fit_is_only_what_the_page_states() -> None:
    assert stated_fit("Relaxed Fit Oxford") == "relaxed" and stated_fit("Oxford shirt") is None
    c = Candidate(piece(), "store", "Oxford shirt", [], {"office": 1})
    assert by_key(judge(c, "office", PROFILE, "slim"))["fit"].ok is None
    loose = Candidate(piece(), "store", "Oversized knit polo", [], {"office": 1})
    r = judge(loose, "office", PROFILE, "slim")
    assert r.verdict == "works" and by_key(r)["fit"].detail == "It’s cut relaxed; you prefer slim."


# ---------------------------------------------------------------- the job


class OnePage(Fetcher):
    def __init__(self, page: Page) -> None:
        super().__init__()
        self.page = page

    def get(self, url: str, *, check_robots: bool = True) -> Page:
        return self.page


def product(name: str, price: float) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "offers": {"price": price, "priceCurrency": "USD", "availability": "InStock"},
    }
    return f'<html><script type="application/ld+json">{json.dumps(data)}</script></html>'


@pytest.fixture(autouse=True)
def public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    real = socket.getaddrinfo

    def fake(host: str, *a: Any, **k: Any) -> Any:
        if host in ("localhost", "router.lan"):
            return real("127.0.0.1", *a, **k)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("23.1.2.3", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake)


def test_a_link_is_read_from_the_store_and_checked(jctx: JobContext, store: Store) -> None:  # noqa: F811
    url = "https://www.gap.com/browse/product.do?pid=1"
    store.wishes["w"] = {"id": "w", "name": "Piece to check", "url": url, "occasion": "office"}
    page = Page(url, 200, product("Slim Navy Knit Polo", 49.5))
    out = suits_me.run({"wish_id": "w", "date": "2026-11-20"}, jctx, vision(), OnePage(page))
    assert out["read"] == {
        "from": "link",
        "type": "knit polo",
        "category": "Tops",
        "color": "navy",
        "color_source": "store",
        "link_note": None,
    }
    assert out["verdict"] in ("strong", "works", "rethink") and out["checks"]
    w = store.wishes["w"]
    assert w["name"] == "Slim Navy Knit Polo" and w["price_cents"] == 4950 and w["store"] == "Gap"
    assert w["check_result"]["suits"]["headline"] == out["headline"]


def test_a_blocked_store_asks_for_a_screenshot(jctx: JobContext, store: Store) -> None:  # noqa: F811
    url = "https://www.zara.com/us/en/shirt-p0123.html"
    store.wishes["w"] = {"id": "w", "name": "Piece to check", "url": url}
    with pytest.raises(BadJob, match=r"blocked the request\. Take a screenshot"):
        suits_me.run({"wish_id": "w"}, jctx, vision(), OnePage(Page(url, 403, reason="blocked")))


def test_private_addresses_are_never_fetched(jctx: JobContext, store: Store) -> None:  # noqa: F811
    assert not suits_me.public_url("http://localhost:8888/search")
    assert not suits_me.public_url("http://router.lan/")
    assert not suits_me.public_url("file:///etc/passwd")
    assert suits_me.public_url("https://www.gap.com/")
    store.wishes["w"] = {"id": "w", "name": "x", "url": "http://localhost:8888/"}
    with pytest.raises(BadJob, match="can’t be opened"):
        suits_me.run({"wish_id": "w"}, jctx, vision(), OnePage(Page("", 200, "")))


def test_type_from_the_product_name() -> None:
    t = suits_me.type_in("The Slim Oxford Shirt | White")
    assert t is not None and t.type == "oxford shirt"
    assert suits_me.type_in("Gift card") is None
    # Real product names from Gap and L.L.Bean (live read, 2026-11-23).
    for name in ("Oxford Button-Down Shirt", "Men's Wrinkle-Free Classic Oxford Cloth Shirt"):
        t = suits_me.type_in(name)
        assert t is not None and t.type == "oxford shirt", name
    chinos = suits_me.type_in("Straight Italian-Stretch Chinos")
    assert chinos is not None and chinos.type == "chinos"
    tee = suits_me.type_in("Organic Cotton Crew T-Shirt")
    assert tee is not None and tee.type == "t-shirt"

"""Deal hunts and price watch, offline: stores, parsing, polite fetching, ranking, honesty."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from closet_worker.shopping import hunt as H
from closet_worker.shopping.fetch import Fetcher, Page
from closet_worker.shopping.parse import Listing, cents, parse_listing
from closet_worker.shopping.stores import canonical, load_stores

# ---------------------------------------------------------------- stores


def test_every_store_pattern_matches_its_real_example() -> None:
    sl = load_stores()
    for s in sl.stores:
        assert sl.product_store(s.example) is s, s.name


@pytest.mark.parametrize(
    "url",
    [
        "https://www.gap.com/browse/women/shirts-and-tops?cid=34608",
        "https://www.jcrew.com/plp/mens/categories/clothing/shirts",
        "https://www.nordstrom.com/browse/men/clothing/shirts",
        "https://www.everlane.com/collections/mens-tshirts",
        "https://shop.mango.com/us/en/p/teen/shirts/oxford-shirt/27011513/50/00",  # teen
        "https://www.example.com/products/shirt",  # not a listed store
        "ftp://www.gap.com/browse/product.do?pid=1",
    ],
)
def test_category_kids_and_unknown_pages_are_not_products(url: str) -> None:
    assert load_stores().product_store(url) is None


def test_canonical_drops_tracking_but_keeps_ids() -> None:
    assert canonical("https://www.gap.com/browse/product.do?pid=6195&vid=1&tid=x") == (
        "https://www.gap.com/browse/product.do?pid=6195"
    )
    assert canonical("https://www.everlane.com/products/x?utm_source=y") == (
        "https://www.everlane.com/products/x"
    )


def test_favorite_names_match_stores() -> None:
    names = [s.name for s in load_stores().match_names(["j.crew", "Uniqlo", "nope", ""])]
    assert names == ["Uniqlo", "J.Crew"]


# ---------------------------------------------------------------- parsing


def page(*jsonld: Any, extra: str = "") -> str:
    blocks = "".join(f'<script type="application/ld+json">{json.dumps(j)}</script>' for j in jsonld)
    return f"<html><head>{blocks}{extra}</head><body></body></html>"


PRODUCT = {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Oxford Shirt",
    "image": ["https://img.example/1.jpg"],
    "brand": {"@type": "Brand", "name": "Gap"},
    "aggregateRating": {"ratingValue": "4.69", "reviewCount": "1240"},
    "offers": [
        {
            "@type": "Offer",
            "price": "39.95",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock",
        },
        {
            "@type": "Offer",
            "price": "35.00",
            "priceCurrency": "USD",
            "availability": "https://schema.org/OutOfStock",
            "priceSpecification": [
                {"priceType": "https://schema.org/StrikethroughPrice", "price": 59.95}
            ],
        },
    ],
}


def test_jsonld_product() -> None:
    it = parse_listing(page(PRODUCT), "https://www.gap.com/browse/product.do?pid=1")
    assert it is not None
    assert (it.title, it.price_cents, it.currency, it.in_stock) == (
        "Oxford Shirt",
        3500,
        "USD",
        True,
    )
    assert (it.was_price_cents, it.rating, it.rating_count, it.brand) == (5995, 4.69, 1240, "Gap")
    assert it.image_url == "https://img.example/1.jpg" and it.source == "jsonld"


def test_product_group_with_sizes_in_a_graph() -> None:
    group = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "BreadcrumbList"},
            {
                "@type": "ProductGroup",
                "name": "Everyday Linen Shirt",
                "hasVariant": [
                    {
                        "@type": "Product",
                        "size": "M",
                        "image": "//cdn.example/m.jpg",
                        "offers": {"price": 110, "priceCurrency": "USD", "availability": "InStock"},
                    },
                    {
                        "@type": "Product",
                        "size": "L",
                        "offers": {
                            "price": 110,
                            "priceCurrency": "USD",
                            "availability": "OutOfStock",
                        },
                    },
                ],
            },
        ],
    }
    it = parse_listing(page(group), "https://bonobos.com/products/x")
    assert it is not None and it.price_cents == 11000 and it.sizes == {"M": True, "L": False}
    assert it.image_url == "https://cdn.example/m.jpg" and it.in_stock is True
    assert H.size_available(it, "m") == "yes" and H.size_available(it, "L") == "no"
    assert H.size_available(it, "XL") == "unknown" and H.size_available(it, None) == "unknown"


def test_opengraph_fallback_and_no_data() -> None:
    og = (
        '<meta property="og:title" content="Linen Shirt">'
        '<meta property="og:image" content="https://img.example/2.jpg">'
        '<meta property="product:price:amount" content="48.00">'
        '<meta property="product:price:currency" content="usd">'
    )
    it = parse_listing(page(extra=og), "https://x.example/p")
    assert it is not None and (it.price_cents, it.currency, it.in_stock, it.source) == (
        4800,
        "USD",
        None,
        "opengraph",
    )
    assert parse_listing("<html><body>Loading…</body></html>", "https://x.example/p") is None
    no_price = {**PRODUCT, "offers": {"priceCurrency": "USD"}}
    assert parse_listing(page(no_price), "https://x.example/p") is None  # never guessed


def test_cents() -> None:
    assert [
        cents("$39.50"),
        cents(39),
        cents("1,299.00"),
        cents("free"),
        cents(None),
        cents(True),
    ] == [
        3950,
        3900,
        129900,
        None,
        None,
        None,
    ]


# ---------------------------------------------------------------- polite fetching


def fetcher(handler: Any, sleeps: list[float]) -> Fetcher:
    t = [0.0]

    def clock() -> float:
        return t[0]

    def sleep(s: float) -> None:
        sleeps.append(s)
        t[0] += s

    return Fetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)), clock=clock, sleep=sleep
    )


def test_robots_rate_limit_and_reasons() -> None:
    seen: list[str] = []
    agents: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.path)
        agents.append(req.headers.get("user-agent", ""))
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        if req.url.path == "/blocked":
            return httpx.Response(403)
        return httpx.Response(200, text="ok")

    sleeps: list[float] = []
    f = fetcher(handler, sleeps)
    assert f.get("https://a.example/private/x").reason == "robots"
    assert f.get("https://a.example/blocked").reason == "blocked"
    assert f.get("https://a.example/fine").ok
    assert seen == ["/robots.txt", "/blocked", "/fine"]  # robots read once, private never fetched
    assert sleeps and all(s <= 1.0 for s in sleeps)  # 1 request per second per site
    assert all("ClosetDealHunter" in ua for ua in agents)  # every request identifies itself


def test_robots_errors_mean_no() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return (
            httpx.Response(503) if req.url.path == "/robots.txt" else httpx.Response(200, text="x")
        )

    assert fetcher(handler, []).get("https://b.example/p").reason == "robots"

    def missing(req: httpx.Request) -> httpx.Response:
        return (
            httpx.Response(404) if req.url.path == "/robots.txt" else httpx.Response(200, text="x")
        )

    assert fetcher(missing, []).get("https://c.example/p").ok  # no robots.txt: allowed


# ---------------------------------------------------------------- hunts


def listing(url: str, title: str, price: int | None, **kw: Any) -> Listing:
    base: dict[str, Any] = {"currency": "USD", "in_stock": True, "image_url": None}
    base.update(kw)
    return Listing(url=url, title=title, price_cents=price, **base)


class FakeFetcher(Fetcher):
    def __init__(self, pages: dict[str, Listing | str]) -> None:
        super().__init__()
        self.pages = pages
        self.asked: list[str] = []

    def get(self, url: str, *, check_robots: bool = True) -> Page:
        self.asked.append(url)
        v = self.pages.get(url)
        if isinstance(v, str):
            return Page(url, 403 if v == "blocked" else 0, reason=v)
        if v is None:
            return Page(url, 200, text="<html></html>")
        return Page(
            url,
            200,
            text=page(
                {
                    "@type": "Product",
                    "name": v.title,
                    "offers": {
                        "price": None if v.price_cents is None else v.price_cents / 100,
                        "priceCurrency": v.currency,
                        "availability": "InStock" if v.in_stock else "OutOfStock",
                    },
                    **(
                        {
                            "offers": {
                                "price": v.price_cents / 100,
                                "priceCurrency": v.currency,
                                "availability": "InStock" if v.in_stock else "OutOfStock",
                                "priceSpecification": {
                                    "priceType": "ListPrice",
                                    "price": v.was_price_cents / 100,
                                },
                            }
                        }
                        if v.was_price_cents
                        else {}
                    ),
                }
            ),
        )


GAP = "https://www.gap.com/browse/product.do?pid={}"
EVER = "https://www.everlane.com/products/{}"
HM = "https://www2.hm.com/en_us/productpage.{}.html"


def run(
    pages: dict[str, Any], urls: list[str], tmp: Path, h: H.Hunt | None = None, fail: bool = False
) -> H.Outcome:
    def search(q: str) -> list[str]:
        if fail:
            raise RuntimeError("down")
        return urls

    return H.run_hunt(
        h or H.Hunt("white oxford shirt", 2500, 6000, wears="menswear"),
        search,
        FakeFetcher(pages),
        lambda items, q: [1.0] * len(items),
        lambda it: (0.0, None, None),
        health_path=tmp / "health.json",
        pause=lambda s: None,
    )


def test_keeps_only_stated_usd_in_stock_in_budget(tmp_path: Path) -> None:
    pages = {
        GAP.format(1): listing(GAP.format(1), "Oxford A", 3900),
        GAP.format(2): listing(GAP.format(2), "Oxford B", 9900),  # over budget
        GAP.format(3): listing(GAP.format(3), "Oxford C", 3000, in_stock=False),
        EVER.format("a"): listing(EVER.format("a"), "Oxford D", 3900, currency="CAD"),
        EVER.format("b"): listing(EVER.format("b"), "Oxford E", 4800, was_price_cents=6000),
        HM.format(1): "blocked",
    }
    out = run(pages, list(pages), tmp_path)
    titles = [p.listing.title for p in out.picks]
    assert titles[0] == "Oxford E" and set(titles) == {
        "Oxford A",
        "Oxford E",
    }  # discount ranks first
    assert (
        out.summary.startswith("2 picks from Everlane and Gap.")
        and "H&M blocked automated reading" in out.summary
    )
    assert H.why_text(out.picks[0], H.Hunt("white oxford shirt", None, None)).endswith(
        "20% off right now."
    )


def test_few_results_and_search_down_are_explained(tmp_path: Path) -> None:
    pages = {GAP.format(1): listing(GAP.format(1), "Oxford A", 9900)}
    out = run(pages, list(pages), tmp_path)
    assert (
        out.picks == [] and "No picks in budget." in out.summary and "wider budget" in out.summary
    )
    down = run({}, [], tmp_path, fail=True)
    assert down.summary.startswith("Search didn’t answer") and down.pages_checked == 0


def test_at_most_two_per_store_and_blocked_stores_rest_a_week(tmp_path: Path) -> None:
    pages: dict[str, Any] = {
        GAP.format(i): listing(GAP.format(i), f"Oxford {i}", 3000 + i) for i in range(4)
    }
    pages[HM.format(1)] = "blocked"
    out = run(pages, list(pages), tmp_path)
    assert [p.store for p in out.picks] == ["Gap", "Gap"]
    health = json.loads((tmp_path / "health.json").read_text())
    assert health["H&M"]["status"] == "blocked" and health["Gap"]["status"] == "ok"
    f = FakeFetcher(pages)
    H.run_hunt(
        H.Hunt("oxford", None, None),
        lambda q: list(pages),
        f,
        lambda i, q: [1.0] * len(i),
        lambda it: (0.0, None, None),
        health_path=tmp_path / "health.json",
        pause=lambda s: None,
    )
    assert HM.format(1) not in f.asked  # skipped: it blocked within the last week
    later = datetime.now(UTC) + timedelta(days=8)
    assert H.recently_blocked(health, "H&M", later) is None


def test_queries() -> None:
    sl = load_stores()
    h = H.Hunt(
        "oxford shirt", None, None, wears="womenswear", best_colors=["light blue", "mint", "navy"]
    )
    q = H.queries(h, list(sl.stores[:3]))
    assert q[:3] == [
        "oxford shirt women",
        "light blue oxford shirt women",
        "mint oxford shirt women",
    ]
    assert q[3] == "site:www.uniqlo.com oxford shirt" and len(q) <= H.MAX_QUERIES
    named = H.queries(
        H.Hunt("white oxford shirt", None, None, wears="both", best_colors=["navy"]), []
    )
    assert named == ["white oxford shirt"]  # already says its color; "both" adds no audience


def test_texts() -> None:
    assert (
        H.quality_text(listing("u", "t", 1, rating=4.66, rating_count=1240))
        == "4.7★ from 1,240 reviews."
    )
    assert H.quality_text(listing("u", "t", 1)) == "No ratings on the page."
    assert H.phrase("white", "white", "neutrals") == "White is one of your neutrals."
    assert (
        H.phrase("sky blue", "light blue", "best colors")
        == "Its sky blue is close to light blue, one of your best colors."
    )
    assert (
        H.color_in("The Must-Have Oxford Shirt | White") == "white"
        and H.color_in("Oxford Shirt") is None
    )


def test_suits_you_drops_careful_colors_near_face_and_sold_out_sizes() -> None:
    h = H.Hunt("oxford shirt", None, None, size="M", careful_colors=("orange",))
    shirt = "https://x.example/p"
    assert not H.keep(listing(shirt, "Orange oxford shirt", 4000, color="Orange"), h)
    assert H.keep(listing(shirt, "Navy oxford shirt", 4000, color="Navy"), h)
    # Away from the face (trousers, shoes), a careful color is fine.
    far = H.Hunt("chinos", None, None, careful_colors=("orange",), near_face=False)
    assert H.keep(listing(shirt, "Orange chinos", 4000, color="Orange"), far)
    # Your size sold out: dropped. Size not listed on the page: kept, never guessed.
    assert not H.keep(listing(shirt, "Navy oxford shirt", 4000, sizes={"M": False, "L": True}), h)
    assert H.keep(listing(shirt, "Navy oxford shirt", 4000, sizes={"L": True}), h)
    assert H.keep(listing(shirt, "Navy oxford shirt", 4000), h)


def test_fit_match_only_counts_stated_fits() -> None:
    assert H.fit_match(listing("u", "Slim-fit oxford shirt", 1), "slim") == 1.0
    assert H.fit_match(listing("u", "Oxford shirt", 1, crumbs=["Men", "Slim fit"]), "slim") == 1.0
    assert H.fit_match(listing("u", "Oxford shirt", 1), "slim") == 0.0
    assert H.fit_match(listing("u", "Slim-fit oxford shirt", 1), None) == 0.0


def test_why_text_puts_what_suits_you_first() -> None:
    p = H.Pick(
        listing("u", "Slim oxford", 4000, was_price_cents=5000),
        "Gap",
        1.0,
        {"match": 0.8, "favorite": 0.0, "fit": 1.0, "size": 1.0},
        palette_note="Navy is one of your best colors.",
    )
    text = H.why_text(p, H.Hunt("oxford shirt", None, None, fit_pref="slim", size="M"))
    assert text == (
        "Navy is one of your best colors. It’s cut slim, your preferred fit. "
        "Your size is in stock. A close match for “oxford shirt”. 20% off right now."
    )
    # Without a fit preference or size, those lines never appear.
    p.parts.update(fit=0.0, size=0.0)
    assert "fit" not in H.why_text(p, H.Hunt("oxford shirt", None, None))


def test_look_slot_sizes() -> None:
    from closet_worker.shopping.look import slot_size

    sizes = {"top": "M", "waist": "32", "inseam": "30", "shoe": "9"}
    assert slot_size("Tops", sizes) == "M"
    assert slot_size("Layers", sizes) == "M"
    assert slot_size("Bottoms", sizes) == "32x30"
    assert slot_size("Bottoms", {"waist": "32"}) == "32"
    assert slot_size("Shoes", sizes) == "9"
    assert slot_size("Accessories", sizes) is None
    assert slot_size("Tops", {}) is None

"""Read a product page's own published data (SPEC 5.8 step 5): schema.org Product (JSON-LD or
microdata), then Open Graph product tags. Only what the page states is returned; a missing
price stays missing (the listing is then skipped), it's never estimated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

IN_STOCK = ("instock", "limitedavailability", "onlineonly", "preorder", "presale", "backorder")
OUT_OF_STOCK = ("outofstock", "soldout", "discontinued")


@dataclass
class Listing:
    url: str
    title: str
    price_cents: int | None
    currency: str | None
    in_stock: bool | None  # None: the page doesn't say
    image_url: str | None = None
    brand: str | None = None
    was_price_cents: int | None = None
    rating: float | None = None
    rating_count: int | None = None
    sizes: dict[str, bool] = field(default_factory=dict)  # size label → in stock
    source: str = "jsonld"  # jsonld | microdata | opengraph


def cents(v: Any) -> int | None:
    if v is None or isinstance(v, bool):
        return None
    s = str(v).strip().replace(",", "")
    s = re.sub(r"^[^\d.]+", "", s)  # "$39.50" → "39.50"
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return int((d * 100).to_integral_value()) if d >= 0 else None


def _first(v: Any) -> Any:
    return v[0] if isinstance(v, list) and v else v


def _text(v: Any) -> str | None:
    v = _first(v)
    if isinstance(v, dict):
        v = v.get("name") or v.get("@value")
    return str(v).strip() if v not in (None, "") else None


def _image(v: Any) -> str | None:
    v = _first(v)
    if isinstance(v, dict):
        v = v.get("url") or v.get("contentUrl")
    s = str(v).strip() if v else ""
    if s.startswith("//"):
        s = "https:" + s
    return s if s.startswith(("http://", "https://")) else None


def _availability(v: Any) -> bool | None:
    s = str(_first(v) or "").lower().rsplit("/", 1)[-1]
    if any(k in s for k in OUT_OF_STOCK):
        return False
    if any(k in s for k in IN_STOCK):
        return True
    return None


def _type_is(node: dict[str, Any], *names: str) -> bool:
    t = node.get("@type")
    types = t if isinstance(t, list) else [t]
    return any(str(x).rsplit("/", 1)[-1] in names for x in types)


def _walk(v: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(v, dict):
        out.append(v)
        for k in ("@graph", "mainEntity", "itemListElement", "item"):
            if k in v:
                out += _walk(v[k])
    elif isinstance(v, list):
        for x in v:
            out += _walk(x)
    return out


def _offers(node: dict[str, Any]) -> list[dict[str, Any]]:
    o = node.get("offers")
    if isinstance(o, dict) and _type_is(o, "AggregateOffer") and "offers" in o:
        inner = o["offers"]
        return ([o] if "lowPrice" in o else []) + (inner if isinstance(inner, list) else [inner])
    return [x for x in (o if isinstance(o, list) else [o]) if isinstance(x, dict)]


def _list_price(offer: dict[str, Any]) -> int | None:
    specs = offer.get("priceSpecification")
    for s in specs if isinstance(specs, list) else [specs]:
        if isinstance(s, dict) and re.search(
            r"(ListPrice|StrikethroughPrice|MSRP)", str(s.get("priceType", ""))
        ):
            return cents(s.get("price"))
    return None


def from_product(node: dict[str, Any], url: str, source: str) -> Listing | None:
    title = _text(node.get("name"))
    if not title:
        return None
    variants = [v for v in _walk(node.get("hasVariant")) if isinstance(v, dict)]
    offers = _offers(node) or [o for v in variants for o in _offers(v)]
    priced: list[tuple[int, dict[str, Any]]] = []
    for o in offers:
        c = cents(o.get("price") or o.get("lowPrice"))
        if c is not None:
            priced.append((c, o))
    price: int | None
    offer: dict[str, Any]
    price, offer = min(priced, key=lambda x: x[0]) if priced else (None, {})
    stock = [_availability(o.get("availability")) for o in offers]
    in_stock = (
        True
        if any(s is True for s in stock)
        else (False if stock and all(s is False for s in stock) else None)
    )
    raw_rating = node.get("aggregateRating")
    rating: dict[str, Any] = raw_rating if isinstance(raw_rating, dict) else {}
    sizes: dict[str, bool] = {}
    for v in variants:
        size = _text(v.get("size"))
        av = [_availability(o.get("availability")) for o in _offers(v)]
        if size and av and av[0] is not None:
            sizes[size] = sizes.get(size, False) or bool(av[0])
    was = _list_price(offer) if offer else None
    try:
        r = float(rating["ratingValue"]) if rating.get("ratingValue") not in (None, "") else None
    except (TypeError, ValueError):
        r = None
    try:
        rc = int(float(rating.get("reviewCount") or rating.get("ratingCount") or 0)) or None
    except (TypeError, ValueError):
        rc = None
    return Listing(
        url=url,
        title=title,
        price_cents=price,
        currency=str(offer.get("priceCurrency") or "").upper() or None,
        in_stock=in_stock,
        image_url=_image(node.get("image"))
        or next((_image(v.get("image")) for v in variants if v.get("image")), None),
        brand=_text(node.get("brand")),
        was_price_cents=was if was and price and was > price else None,
        rating=r if r is not None and 0 < r <= 5 else None,
        rating_count=rc,
        sizes=sizes,
        source=source,
    )


def _og(data: dict[str, Any]) -> dict[str, str]:
    """Open Graph tags. extruct gives {"og:title": …} with uniform=True, or a properties list."""
    out: dict[str, str] = {}
    for block in data.get("opengraph") or []:
        pairs = block.get("properties") if "properties" in block else block.items()
        for k, v in pairs or []:
            if isinstance(k, str) and not k.startswith("@"):
                out.setdefault(k, str(_first(v)))
    return out


def parse_listing(html: str, url: str) -> Listing | None:
    """The page's product, or None if it publishes no product data."""
    import extruct  # type: ignore[import-untyped]

    try:
        data = extruct.extract(
            html,
            base_url=url,
            syntaxes=["json-ld", "microdata", "opengraph"],
            errors="ignore",
            uniform=True,
        )
    except Exception:
        return None
    for syntax in ("json-ld", "microdata"):
        for node in _walk(data.get(syntax) or []):
            if _type_is(node, "Product", "ProductGroup", "IndividualProduct"):
                got = from_product(node, url, "jsonld" if syntax == "json-ld" else "microdata")
                if got is not None and got.price_cents is not None:
                    return got
    og = _og(data)
    title = og.get("og:title")
    price = cents(og.get("product:price:amount") or og.get("og:price:amount"))
    if title and price is not None:
        avail = og.get("product:availability") or og.get("og:availability")
        return Listing(
            url=url,
            title=title.strip(),
            price_cents=price,
            currency=(og.get("product:price:currency") or og.get("og:price:currency") or "").upper()
            or None,
            in_stock=_availability(avail) if avail else None,
            image_url=_image(og.get("og:image")),
            brand=og.get("product:brand"),
            source="opengraph",
        )
    return None

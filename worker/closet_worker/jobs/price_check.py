"""`price_check` (SPEC 5.9): daily at 09:00, rechecks watched wishlist links.

A failed check is saved as "couldn’t check" with the reason; no price is ever guessed.
The web app flags a drop from last_seen_price_cents (target reached, or ≥15% below the price
you added).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from closet_worker.shopping.fetch import Fetcher
from closet_worker.shopping.parse import parse_listing

from .context import JobContext
from .tag_item import BadJob

REASONS = {
    "robots": "the store doesn’t allow automated reading",
    "blocked": "the store blocked the check",
    "not_found": "the page is gone",
    "timeout": "the store didn’t answer in time",
    "error": "the store returned an error",
    "too_big": "the page was too large to read",
}


def check_one(wish: dict[str, Any], fetcher: Fetcher) -> dict[str, Any]:
    page = fetcher.get(str(wish["url"]))
    if not page.ok:
        return {
            "price_cents": None,
            "in_stock": None,
            "source": None,
            "note": f"Couldn’t check: {REASONS.get(page.reason, page.reason)}.",
        }
    item = parse_listing(page.text, page.url)
    if item is None or item.price_cents is None:
        return {
            "price_cents": None,
            "in_stock": None,
            "source": None,
            "note": "Couldn’t check: the page doesn’t list a price we can read.",
        }
    if item.currency not in (None, "USD"):
        return {
            "price_cents": None,
            "in_stock": item.in_stock,
            "source": None,
            "note": f"Couldn’t check: the price is in {item.currency}, not USD.",
        }
    return {
        "price_cents": item.price_cents,
        "in_stock": item.in_stock,
        "source": "opengraph" if item.source == "opengraph" else "jsonld",
        "note": None,
    }


def run(
    payload: dict[str, Any], ctx: JobContext | None, fetcher: Fetcher | None = None
) -> dict[str, Any]:
    if ctx is None or ctx.items is None:
        raise BadJob("no item store")
    f = fetcher or Fetcher()
    checked = ok = 0
    for wish in ctx.items.list_watched_wishes():
        r = check_one(wish, f)
        stamp = datetime.now(UTC).isoformat()
        ctx.items.insert_price_check({"wishlist_id": wish["id"], "checked_at": stamp, **r})
        fields: dict[str, Any] = {"last_price_check_at": stamp}
        if r["price_cents"] is not None:
            fields["last_seen_price_cents"] = r["price_cents"]
            ok += 1
        ctx.items.update_wish(str(wish["id"]), fields)
        checked += 1
    return {"checked": checked, "priced": ok}

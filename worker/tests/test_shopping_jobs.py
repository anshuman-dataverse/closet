"""run_hunt and price_check handlers with an in-memory store."""

from __future__ import annotations

from typing import Any

import pytest

from closet_worker.config import Settings
from closet_worker.jobs import price_check, run_hunt
from closet_worker.jobs.context import JobContext
from closet_worker.jobs.tag_item import BadJob
from closet_worker.shopping import hunt as H
from closet_worker.shopping.fetch import Page
from closet_worker.shopping.parse import Listing

from .conftest import OWNER


class Store:
    owner = OWNER

    def __init__(self) -> None:
        self.hunts = {
            "h1": {
                "id": "h1",
                "query": "oxford shirt",
                "budget_min_cents": 2500,
                "budget_max_cents": 6000,
            }
        }
        self.updates: list[dict[str, Any]] = []
        self.results: dict[str, list[dict[str, Any]]] = {}
        self.wishes = [
            {"id": "w1", "url": "https://www.gap.com/browse/product.do?pid=1", "price_cents": 5000},
            {
                "id": "w2",
                "url": "https://www2.hm.com/en_us/productpage.1.html",
                "price_cents": 3000,
            },
        ]
        self.checks: list[dict[str, Any]] = []
        self.wish_updates: dict[str, dict[str, Any]] = {}

    def get_hunt(self, hunt_id: str) -> dict[str, Any] | None:
        return self.hunts.get(hunt_id)

    def update_hunt(self, hunt_id: str, fields: dict[str, Any]) -> None:
        self.updates.append(fields)

    def replace_hunt_results(self, hunt_id: str, rows: list[dict[str, Any]]) -> None:
        self.results[hunt_id] = rows

    def get_profile(self) -> dict[str, Any]:
        return {"wears": "menswear", "sizes": {"top": "M"}, "favorite_stores": ["Gap"]}

    def list_watched_wishes(self) -> list[dict[str, Any]]:
        return self.wishes

    def insert_price_check(self, row: dict[str, Any]) -> None:
        self.checks.append(row)

    def update_wish(self, wish_id: str, fields: dict[str, Any]) -> None:
        self.wish_updates[wish_id] = fields


def test_run_hunt_writes_status_summary_and_picks(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    pick = H.Pick(
        Listing(
            "https://www.gap.com/browse/product.do?pid=1",
            "Oxford Shirt",
            3900,
            "USD",
            True,
            rating=4.7,
            rating_count=1240,
            sizes={"M": True},
        ),
        "Gap",
        0.9,
        {"match": 1.0, "palette": 0.0, "discount": 0.0, "rating": 0.9, "favorite": 1.0},
    )
    monkeypatch.setattr(
        run_hunt.H, "run_hunt", lambda *a, **k: H.Outcome([pick], 7, {}, 3, "1 pick from Gap.")
    )
    monkeypatch.setattr("closet_worker.vision.embed.load_embedder", lambda *a, **k: None)
    store = Store()
    out = run_hunt.run({"hunt_id": "h1"}, JobContext(settings=settings, items=store))  # type: ignore[arg-type]
    assert out == {"picks": 1, "summary": "1 pick from Gap.", "pages_checked": 7}
    assert store.updates[0]["status"] == "running" and store.updates[-1]["status"] == "done"
    r = store.results["h1"][0]
    assert (r["rank"], r["store"], r["price_cents"], r["quality"], r["size_available"]) == (
        1,
        "Gap",
        3900,
        "4.7★ from 1,240 reviews.",
        "yes",
    )
    assert "From Gap, one of your stores." in r["why"]
    with pytest.raises(BadJob, match="no longer exists"):
        run_hunt.run({"hunt_id": "nope"}, JobContext(settings=settings, items=store))  # type: ignore[arg-type]


def test_run_hunt_marks_failure(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: Any, **k: Any) -> H.Outcome:
        raise RuntimeError("network")

    monkeypatch.setattr(run_hunt.H, "run_hunt", boom)
    monkeypatch.setattr("closet_worker.vision.embed.load_embedder", lambda *a, **k: None)
    store = Store()
    with pytest.raises(RuntimeError):
        run_hunt.run({"hunt_id": "h1"}, JobContext(settings=settings, items=store))  # type: ignore[arg-type]
    assert store.updates[-1]["status"] == "failed" and store.updates[-1]["error"] == "network"


class Fetch:
    def get(self, url: str, *, check_robots: bool = True) -> Page:
        if "hm.com" in url:
            return Page(url, 403, reason="blocked")
        html = (
            '<script type="application/ld+json">{"@type":"Product","name":"Oxford",'
            '"offers":{"price":"39.00","priceCurrency":"USD","availability":"InStock"}}</script>'
        )
        return Page(url, 200, text=html)


def test_price_check_records_prices_and_honest_failures(settings: Settings) -> None:
    store = Store()
    out = price_check.run({}, JobContext(settings=settings, items=store), Fetch())  # type: ignore[arg-type]
    assert out == {"checked": 2, "priced": 1}
    gap, hm = store.checks
    assert (gap["price_cents"], gap["in_stock"], gap["source"], gap["note"]) == (
        3900,
        True,
        "jsonld",
        None,
    )
    assert (
        hm["price_cents"] is None and hm["note"] == "Couldn’t check: the store blocked the check."
    )
    assert store.wish_updates["w1"]["last_seen_price_cents"] == 3900
    assert "last_seen_price_cents" not in store.wish_updates["w2"]  # no guessed price

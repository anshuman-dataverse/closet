from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from closet_worker.config import Settings
from closet_worker.jobs import check_wish, find_gaps, suggest_outfits
from closet_worker.jobs.context import JobContext

from .conftest import OWNER
from .stubs import StubEmbedder


def rows() -> list[dict[str, Any]]:
    base = [
        (
            "navy-oxford",
            "Navy oxford shirt",
            "Tops",
            "oxford shirt",
            "navy",
            3,
            "light",
            3950,
            "2026-11-02",
        ),
        (
            "white-oxford",
            "White oxford shirt",
            "Tops",
            "oxford shirt",
            "white",
            3,
            "light",
            3200,
            "2026-09-01",
        ),
        (
            "grey-chinos",
            "Grey chinos",
            "Bottoms",
            "chinos",
            "grey",
            3,
            "medium",
            4800,
            "2026-08-01",
        ),
        ("khaki-chinos", "Khaki chinos", "Bottoms", "chinos", "khaki", 3, "medium", None, None),
        (
            "navy-trousers",
            "Navy trousers",
            "Bottoms",
            "dress trousers",
            "navy",
            4,
            "medium",
            None,
            None,
        ),
        (
            "boots",
            "Brown chelsea boots",
            "Shoes",
            "chelsea boots",
            "brown",
            3,
            "warm",
            12000,
            "2026-10-10",
        ),
    ]
    return [
        {
            "id": i,
            "name": n,
            "category": c,
            "type": t,
            "color_name": col,
            "formality": f,
            "warmth": w,
            "occasions": ["office"],
            "status": "active",
            "price_cents": pr,
            "bought_on": b,
            "user_id": OWNER,
        }
        for i, n, c, t, col, f, w, pr, b in base
    ]


class Store:
    owner = OWNER

    def __init__(self) -> None:
        self.items = rows()
        self.events: list[dict[str, Any]] = []
        self.wishes: dict[str, dict[str, Any]] = {}
        self.near: list[dict[str, Any]] = []
        self.logs: list[dict[str, Any]] = [
            {"id": "w1", "worn_on": "2026-11-18", "item_ids": ["navy-oxford"]}
        ]

    def list_items(self) -> list[dict[str, Any]]:
        return self.items

    def list_wear_logs(self) -> list[dict[str, Any]]:
        return self.logs

    def list_outfits(self) -> list[dict[str, Any]]:
        return []

    def get_profile(self) -> dict[str, Any]:
        return {"timezone": "America/New_York", "monthly_budget_cents": 15000}

    def insert_events(self, rs: list[dict[str, Any]]) -> list[str]:
        self.events += rs
        return [f"e{len(self.events) - len(rs) + k}" for k in range(len(rs))]

    def get_wish(self, wid: str) -> dict[str, Any] | None:
        return self.wishes.get(wid)

    def update_wish(self, wid: str, fields: dict[str, Any]) -> None:
        self.wishes[wid].update(fields)

    def nearest_items(self, vec: list[float], category: str | None, k: int) -> list[dict[str, Any]]:
        return self.near

    def download(self, path: str) -> bytes:
        raise AssertionError("no photo in these tests")


@pytest.fixture
def store() -> Store:
    return Store()


@pytest.fixture
def jctx(settings: Settings, store: Store) -> JobContext:
    return JobContext(settings=settings, items=store)  # type: ignore[arg-type]


def test_suggest_outfits_logs_shown_events(jctx: JobContext, store: Store) -> None:
    out = suggest_outfits.run(
        {
            "occasion": "office",
            "date": "2026-11-20",
            "weather": {"high": 45, "unit": "F", "rain_pct": 10},
            "note": "lunch with the team",
        },
        jctx,
    )
    assert 1 <= len(out["ideas"]) <= 3 and out["bar"]["message"] is None
    assert [e["action"] for e in store.events] == ["shown"] * len(out["ideas"])
    first = out["ideas"][0]
    assert first["event_id"] == "e0" and first["text"].endswith(".")
    assert store.events[0]["item_ids"] == first["item_ids"]
    assert store.events[0]["context"]["note"] == "lunch with the team"


def test_nothing_shown_when_nothing_passes_and_it_says_why(jctx: JobContext, store: Store) -> None:
    # A client meeting raises the bar; this closet has nothing formal enough.
    out = suggest_outfits.run(
        {"occasion": "office", "date": "2026-11-20", "note": "client meeting"}, jctx
    )
    assert out["ideas"] == [] and store.events == []
    assert out["bar"]["top_fail"] == "formality" and out["bar"]["candidates"] > 0
    assert out["bar"]["message"] == (
        "No combination from your closet passes every check today: most often, "
        "the pieces don’t suit the occasion."
    )


def _wish(store: Store, **kw: Any) -> str:
    store.wishes["w"] = {
        "id": "w",
        "name": "Light blue oxford shirt",
        "category": "Tops",
        "color_name": "light blue",
        "occasion": "office",
        "price_cents": 5000,
        **kw,
    }
    return "w"


def test_check_wish_buy_when_new_and_useful(jctx: JobContext, store: Store) -> None:
    res = check_wish.run({"wish_id": _wish(store), "date": "2026-11-20"}, jctx, emb=StubEmbedder())  # type: ignore[arg-type]
    assert res["verdict"] == "buy" and res["unlocks"] >= 3 and res["embedding_kind"] == "text"
    assert store.wishes["w"]["check_result"]["verdict"] == "buy"
    assert len(store.wishes["w"]["embedding"]) == 32


def test_check_wish_skip_for_a_worn_duplicate(jctx: JobContext, store: Store) -> None:
    store.near = [{"item_id": "navy-oxford", "similarity": 0.95}]
    res = check_wish.run({"wish_id": _wish(store), "date": "2026-11-20"}, jctx, emb=StubEmbedder())  # type: ignore[arg-type]
    assert res["verdict"] == "skip" and res["duplicates"][0]["wears"] == 1
    assert res["reasons"][0].startswith("You own something very similar")


def test_check_wish_skip_when_over_budget(jctx: JobContext, store: Store) -> None:
    res = check_wish.run(
        {"wish_id": _wish(store, price_cents=90000), "date": "2026-11-20"}, jctx, emb=StubEmbedder()
    )  # type: ignore[arg-type]
    assert res["verdict"] == "skip" and res["over_budget_cents"] > 0


def test_find_gaps_spreads_categories_and_skips_owned(jctx: JobContext) -> None:
    out = find_gaps.run({"occasion": "office", "date": "2026-11-20"}, jctx)["ideas"]
    assert 3 <= len(out) <= 5
    cats = [i["category"] for i in out]
    assert all(cats.count(c) <= 2 for c in cats)
    assert not any(
        i["type"] == "oxford shirt" and i["color_name"] == "white" for i in out
    )  # already owned
    assert all(
        i["price_min_cents"] < i["price_max_cents"] and i["reason"].startswith("Adds ") for i in out
    )


def test_stub_embedder_is_normalized() -> None:
    v = StubEmbedder().text(["x"])[0]
    assert np.isclose(np.linalg.norm(v), 1.0)

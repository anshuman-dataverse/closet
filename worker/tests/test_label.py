"""Label reading (vision/label.py, jobs/read_label.py): only what's printed, never a guess."""

from __future__ import annotations

from typing import Any

import pytest

from closet_worker.config import Settings
from closet_worker.jobs import read_label
from closet_worker.jobs.context import JobContext
from closet_worker.jobs.tag_item import BadJob
from closet_worker.vision.label import Line, parse

from .conftest import OWNER


def lines(*texts: str, big: str | None = None) -> list[Line]:
    out = [Line(t, 0.95, 0.04) for t in texts]
    if big:
        out.insert(0, Line(big, 0.98, 0.15))
    return out


def test_jeans_label() -> None:
    r = parse(
        lines(
            "W32 L30", "Relaxed fit", "98% Cotton 2% Elastane", "Made in Bangladesh", big="Levi's"
        )
    )
    assert (r.brand, r.size, r.fit) == ("Levi's", "W32 L30", "relaxed")
    assert r.materials_text == "98% cotton, 2% elastane"


def test_multilingual_composition_counts_once() -> None:
    r = parse(
        lines("100% COTTON", "100% COTON", "100% BAUMWOLLE", "100% ALGODÓN", "SIZE M", big="UNIQLO")
    )
    assert (
        r.materials == [{"fiber": "cotton", "pct": 100}] and r.size == "M" and r.brand == "UNIQLO"
    )


def test_fiber_first_and_synonyms() -> None:
    r = parse(lines("COTTON 60%", "POLYESTER 35%", "SPANDEX 5%"))
    assert r.materials_text == "60% cotton, 35% polyester, 5% elastane"


def test_partial_composition_is_left_out() -> None:
    r = parse(lines("Shell: 80% wool", "Lining: 100% polyester"))  # two parts, 180% total
    assert r.materials == [] and any("100%" in n for n in r.notes)


def test_size_chart_gives_no_size() -> None:
    r = parse(lines("S", "M", "L", "XL"))
    assert r.size is None and any("more than one size" in n for n in r.notes)


def test_waist_inseam_formats() -> None:
    assert parse(lines("32x34")).size == "W32 L34"
    assert parse(lines("33W 32L")).size == "W33 L32"
    assert parse(lines("120x200 cm")).size is None  # not a waist/inseam


def test_fit_words() -> None:
    assert parse(lines("SLIM FIT")).fit == "slim"
    assert parse(lines("Wide leg")).fit == "wide"
    assert parse(lines("Boot cut")).fit == "bootcut"
    assert parse(lines("Oversized")).fit == "oversized"
    r = parse(lines("Slim fit", "Relaxed"))
    assert r.fit is None and any("more than one fit" in n for n in r.notes)
    assert parse(lines("Fitzgerald")).fit is None  # word boundaries


def test_care_and_numbers_are_not_the_brand() -> None:
    r = parse(lines("MACHINE WASH COLD", "RN 12345", "DO NOT BLEACH"))
    assert r.brand is None


def test_low_confidence_text_is_ignored() -> None:
    r = parse([Line("W32 L30", 0.2, 0.05), Line("Zara", 0.9, 0.1)])
    assert r.size is None and r.brand == "Zara"


ITEM = "9b1c0000-0000-4000-8000-0000000000aa"
LABEL = f"{OWNER}/items/{ITEM}/label-1.jpg"


class Store:
    owner = OWNER

    def __init__(self) -> None:
        self.item: dict[str, Any] = {
            "id": ITEM,
            "label_path": LABEL,
            "suggestions": {"type": "jeans", "status": "ready"},
        }

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        return self.item if item_id == ITEM else None

    def download(self, path: str) -> bytes:
        return b"jpeg"

    def update_item(self, item_id: str, fields: dict[str, Any]) -> None:
        self.item.update(fields)


class Reader:
    def __init__(self, ls: list[Line]) -> None:
        self.ls = ls

    def read(self, image: bytes) -> list[Line]:
        return self.ls


def test_job_keeps_photo_suggestions_and_adds_the_label(settings: Settings) -> None:
    store = Store()
    ctx = JobContext(settings=settings, items=store)  # type: ignore[arg-type]
    out = read_label.run({"item_id": ITEM}, ctx, Reader(lines("W32 L30", big="Levi's")))
    assert out["label"]["size"] == "W32 L30"
    assert store.item["suggestions"]["type"] == "jeans"  # the photo's tags stay
    assert store.item["suggestions"]["label"]["brand"] == "Levi's"
    empty = read_label.run({"item_id": ITEM}, ctx, Reader([]))
    assert any("no text found" in n for n in empty["label"]["notes"])


@pytest.mark.parametrize(
    ("payload", "msg"),
    [
        ({"item_id": "nope"}, "no longer exists"),
        ({"item_id": ITEM, "label_path": "someone-else/items/x/label.jpg"}, "isn’t this piece’s"),
    ],
)
def test_bad_jobs(settings: Settings, payload: dict[str, Any], msg: str) -> None:
    ctx = JobContext(settings=settings, items=Store())  # type: ignore[arg-type]
    with pytest.raises(BadJob, match=msg):
        read_label.run(payload, ctx, Reader([]))


def test_mixed_order_on_one_line() -> None:
    assert parse(lines("COTTON 60% POLYESTER 40%")).materials_text == "60% cotton, 40% polyester"
    assert parse(lines("Shell: 98% cotton 2% elastane")).materials_text == "98% cotton, 2% elastane"

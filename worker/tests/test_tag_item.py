from __future__ import annotations

import io
from typing import Any

import pytest
from PIL import Image

from closet_worker.config import Settings
from closet_worker.jobs import tag_item
from closet_worker.jobs.context import JobContext
from closet_worker.jobs.tag_item import BadJob, Vision
from closet_worker.vision.color import Palette
from closet_worker.vision.tagger import TextBank
from closet_worker.vocab import load_vocab

from .conftest import OWNER
from .stubs import StubCutter, StubEmbedder, two_color_image

ITEM = "9b1c0000-0000-4000-8000-000000000001"
PHOTO = f"{OWNER}/items/{ITEM}/abc.jpg"


class MemoryStore:
    owner = OWNER

    def __init__(self) -> None:
        buf = io.BytesIO()
        two_color_image((31, 42, 72), (31, 42, 72), 0, 200).save(buf, "JPEG")
        self.files: dict[str, bytes] = {PHOTO: buf.getvalue()}
        self.items: dict[str, dict[str, Any]] = {
            ITEM: {"id": ITEM, "photo_path": PHOTO, "user_id": OWNER}
        }
        self.embeddings: dict[str, tuple[str, list[float]]] = {}
        self.updates = 0

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        return self.items.get(item_id)

    def list_items(self) -> list[dict[str, Any]]:
        return list(self.items.values())

    def update_item(self, item_id: str, fields: dict[str, Any]) -> None:
        self.items[item_id].update(fields)
        self.updates += 1

    def download(self, path: str) -> bytes:
        return self.files[path]

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        self.files[path] = data

    def upsert_embedding(self, item_id: str, model: str, vec: list[float]) -> None:
        self.embeddings[item_id] = (model, vec)


@pytest.fixture
def ctx(settings: Settings) -> JobContext:
    return JobContext(settings=settings, items=MemoryStore())


def vision() -> Vision:
    emb = StubEmbedder("a photo of a oxford shirt")
    v = load_vocab()
    return Vision(StubCutter(), emb, TextBank(emb, v), Palette.from_dict(v.colors))  # type: ignore[arg-type]


def test_writes_suggestions_cutout_and_embedding(ctx: JobContext) -> None:
    out = tag_item.run({"item_id": ITEM}, ctx, vision())
    store: MemoryStore = ctx.items  # type: ignore[assignment]
    item = store.items[ITEM]
    assert out["suggestions"]["type"] == "oxford shirt"
    assert item["tags_status"] == "ready"
    assert item["suggestions"]["name"] == "Navy oxford shirt"
    cut = f"{OWNER}/items/{ITEM}/abc_cutout.webp"
    assert item["cutout_path"] == cut and Image.open(io.BytesIO(store.files[cut])).mode == "RGBA"
    assert store.embeddings[ITEM][0] == "stub" and len(store.embeddings[ITEM][1]) == 32


def test_is_idempotent(ctx: JobContext) -> None:
    a = tag_item.run({"item_id": ITEM}, ctx, vision())
    b = tag_item.run({"item_id": ITEM}, ctx, vision())
    store: MemoryStore = ctx.items  # type: ignore[assignment]
    assert a == b and len(store.files) == 2 and len(store.embeddings) == 1


def test_unsaved_photo_does_not_replace_the_items_cutout(ctx: JobContext) -> None:
    store: MemoryStore = ctx.items  # type: ignore[assignment]
    new = f"{OWNER}/items/{ITEM}/new.jpg"
    store.files[new] = store.files[PHOTO]
    out = tag_item.run({"item_id": ITEM, "photo_path": new}, ctx, vision())
    assert out["cutout_path"].endswith("new_cutout.webp")
    assert "cutout_path" not in store.items[ITEM] and store.items[ITEM]["suggestions"]


@pytest.mark.parametrize(
    ("payload", "msg"),
    [
        ({"item_id": "nope"}, "no longer exists"),
        ({"item_id": ITEM, "photo_path": f"{OWNER}/items/other/x.jpg"}, "isn’t this piece’s"),
        ({"item_id": ITEM, "photo_path": f"someone-else/items/{ITEM}/x.jpg"}, "isn’t this piece’s"),
    ],
)
def test_bad_jobs_fail_clearly(ctx: JobContext, payload: dict[str, Any], msg: str) -> None:
    with pytest.raises(BadJob, match=msg):
        tag_item.run(payload, ctx, vision())


def test_fake_mode_writes_fixture(ctx: JobContext) -> None:
    from closet_worker import fakes

    out = fakes.run("tag_item", {"item_id": ITEM, "photo_path": PHOTO}, ctx)
    store: MemoryStore = ctx.items  # type: ignore[assignment]
    assert out["suggestions"]["name"] == "Navy oxford shirt"
    assert store.items[ITEM]["tags_status"] == "ready"

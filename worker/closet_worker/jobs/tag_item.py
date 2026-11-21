"""`tag_item` (SPEC 5.1): cutout, embedding, zero-shot tags and color for one piece."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any

from PIL import Image

from closet_worker.vision.color import Palette
from closet_worker.vision.cutout import Cutter
from closet_worker.vision.embed import Embedder, load_embedder
from closet_worker.vision.fit import gate_key, guess_fit, read_gate
from closet_worker.vision.tagger import TextBank, tag
from closet_worker.vocab import load_vocab

from .context import JobContext


class BadJob(Exception):
    """The job can't run as asked (missing item or photo). Not retried."""


@dataclass
class Vision:
    cutter: Cutter
    emb: Embedder
    bank: TextBank
    palette: Palette


_vision: dict[str, Vision] = {}


def vision_for(model_id: str, device: str) -> Vision:
    v = _vision.get(model_id)
    if v is None:
        emb = load_embedder(model_id, device)
        vocab = load_vocab()
        v = Vision(Cutter(), emb, TextBank(emb, vocab), Palette.from_dict(vocab.colors))
        _vision[model_id] = v
    return v


def cutout_path_for(photo_path: str) -> str:
    return re.sub(r"\.jpe?g$", "", photo_path) + "_cutout.webp"


def run(
    payload: dict[str, Any], ctx: JobContext | None, vision: Vision | None = None
) -> dict[str, Any]:
    if ctx is None or ctx.items is None:
        raise BadJob("no item store")
    item_id = str(payload.get("item_id", ""))
    item = ctx.items.get_item(item_id)
    if item is None:
        raise BadJob("That piece no longer exists.")
    photo = str(payload.get("photo_path") or item.get("photo_path") or "")
    if not photo:
        raise BadJob("That piece has no photo yet.")
    if not photo.startswith(f"{ctx.items.owner}/items/{item_id}/") or not photo.endswith(".jpg"):
        raise BadJob("That photo isn’t this piece’s.")

    v = vision or vision_for(ctx.settings.embed_model, ctx.settings.device)
    img = Image.open(io.BytesIO(ctx.items.download(photo))).convert("RGB")
    cut = v.cutter.cut(img)
    cut_path = cutout_path_for(photo)
    ctx.items.upload(cut_path, cut.webp, "image/webp")

    sug, vec = tag(cut.crop, cut.rgb, cut.mask, v.emb, v.bank, v.palette)
    ctx.items.upsert_embedding(item_id, v.emb.model_id, [float(x) for x in vec])

    sug_json = sug.to_json()
    if isinstance(item.get("suggestions"), dict) and "label" in item["suggestions"]:
        sug_json["label"] = item["suggestions"]["label"]  # keep the label read
    fit = suggested_fit(ctx, item, sug_json, vec, cut.mask, v.emb)
    if fit:
        sug_json["fit"] = fit
    fields: dict[str, Any] = {"suggestions": sug_json, "tags_status": sug.status}
    if photo == item.get("photo_path"):  # the saved photo: the cutout belongs to the item now
        fields["cutout_path"] = cut_path
    ctx.items.update_item(item_id, fields)
    return {"suggestions": sug_json, "cutout_path": cut_path, "photo_path": photo}


def suggested_fit(
    ctx: JobContext,
    item: dict[str, Any],
    sug: dict[str, Any],
    vec: Any,
    mask: Any,
    emb: Embedder,
) -> str | None:
    """A fit only when the eval measured that fit as reliable on your photos; else nothing."""
    enabled = read_gate(ctx.settings.fit_gate_path, emb.model_id)
    if not enabled or sug.get("status") == "not_clothing" or ctx.items is None:
        return None
    category = item.get("category") or sug.get("category")
    kind = str(item.get("type") or sug.get("type") or "")
    wears = (ctx.items.get_profile() or {}).get("wears")
    g = guess_fit(vec, mask, category, kind, wears, emb)
    if g is None or g.fit is None or gate_key(category, g.fit) not in enabled:
        return None
    return g.fit

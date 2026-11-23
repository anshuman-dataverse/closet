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
from closet_worker.vision.heads import Heads, HeadsError
from closet_worker.vision.heads import load as load_heads
from closet_worker.vision.studio import make_studio
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


def studio_path_for(photo_path: str) -> str:
    return re.sub(r"\.jpe?g$", "", photo_path) + "_studio.jpg"


def studio_thumb(studio_path: str) -> str:
    return studio_path.removesuffix(".jpg") + "_thumb.jpg"


def save_studio(ctx: JobContext, photo: str, cut: Any) -> str | None:
    """Upload the studio image and its thumbnail; None when there's no usable cut-out."""
    assert ctx.items is not None
    st = make_studio(cut.rgb, cut.mask)
    if st is None:
        return None
    path = studio_path_for(photo)
    ctx.items.upload(path, st.full, "image/jpeg")
    ctx.items.upload(studio_thumb(path), st.thumb, "image/jpeg")
    return path


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
    studio = save_studio(ctx, photo, cut)

    sug, vec = tag(cut.crop, cut.rgb, cut.mask, v.emb, v.bank, v.palette)
    ctx.items.upsert_embedding(item_id, v.emb.model_id, [float(x) for x in vec])

    sug_json = sug.to_json()
    heads = heads_for(ctx, v.emb.model_id)
    if heads is not None and sug.status != "not_clothing":
        apply_heads(sug_json, vec, heads, v.palette.names)
    if isinstance(item.get("suggestions"), dict) and "label" in item["suggestions"]:
        sug_json["label"] = item["suggestions"]["label"]  # keep the label read
    fit = (heads_fit(heads, item, sug_json, vec) if heads else None) or suggested_fit(
        ctx, item, sug_json, vec, cut.mask, v.emb
    )
    if fit:
        sug_json["fit"] = fit
    fields: dict[str, Any] = {"suggestions": sug_json, "tags_status": sug.status}
    if photo == item.get("photo_path"):  # the saved photo: the cutout belongs to the item now
        fields["cutout_path"] = cut_path
        fields["studio_path"] = studio
    ctx.items.update_item(item_id, fields)
    return {
        "suggestions": sug_json,
        "cutout_path": cut_path,
        "studio_path": studio,
        "photo_path": photo,
    }


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


GENERIC_NOUN = {
    "Tops": "top",
    "Bottoms": "pants",
    "Layers": "layer",
    "Shoes": "shoes",
    "Accessories": "accessory",
    "Sets & suits": "set",
}
_heads: dict[str, tuple[tuple[int, int], Heads | None]] = {}


def heads_for(ctx: JobContext, model_id: str) -> Heads | None:
    """Installed heads for this embedding model, cached until the files change."""
    folder = ctx.settings.heads_dir
    try:
        key = (
            (folder / "heads.json").stat().st_mtime_ns,
            (folder / "heads.safetensors").stat().st_mtime_ns,
        )
    except OSError:
        return None
    hit = _heads.get(str(folder))
    if hit and hit[0] == key:
        return hit[1]
    try:
        h = load_heads(folder, model_id)
    except HeadsError as e:
        import logging

        logging.getLogger(__name__).warning("garment heads not used: %s", e)
        h = None
    _heads[str(folder)] = (key, h)
    return h


def apply_heads(
    sug: dict[str, Any], vec: Any, heads: Heads, palette_names: tuple[str, ...]
) -> None:
    """Replace zero-shot guesses only where a head beat them on your photos. Records sources."""
    vocab = load_vocab()
    by_type = {t.type: t for t in vocab.types}
    sources = sug.setdefault("sources", {})
    t = heads.suggest("type", vec)
    entry = by_type.get(t) if t else None
    if entry is not None:
        from closet_worker.vision.tagger import display_name

        color = str(sug.get("color_name") or "").lower()
        name = (
            display_name(color, entry, palette_names)
            if color
            else entry.type[0].upper() + entry.type[1:]
        )
        sug.update(
            type=entry.type,
            category=entry.category,
            formality=entry.formality,
            warmth=entry.warmth,
            occasions=list(entry.occasions),
            name=name,
        )
        sources.update(type="head", category="head")
    else:
        c = heads.suggest("category", vec)
        if c and c != sug.get("category"):
            # The zero-shot type belongs to another category, so it can't stand: ask for it.
            color = str(sug.get("color_name") or "")
            sug.update(category=c, type="", name=f"{color} {GENERIC_NOUN.get(c, 'piece')}".strip())
            sug["status"] = "unsure"
            sources["category"] = "head"
    p = heads.suggest("pattern", vec)
    if p:
        sug["pattern"] = p
        sources["pattern"] = "head"


def heads_fit(heads: Heads, item: dict[str, Any], sug: dict[str, Any], vec: Any) -> str | None:
    from closet_worker.vision.fit import load_fits

    category = item.get("category") or sug.get("category")
    g = load_fits().group_for(category)
    if g is None or g.name not in ("tops", "bottoms"):
        return None
    f = heads.suggest(f"fit/{g.name}", vec)
    if f:
        sug.setdefault("sources", {})["fit"] = "head"
    return f

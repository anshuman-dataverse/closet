"""`check_wish` and `embed_wish` (SPEC 5.6): near-duplicates, unlocks, budget, verdict."""

from __future__ import annotations

import io
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from PIL import Image

from closet_worker.recsys.engine import good_outfits_with, verdict
from closet_worker.recsys.model import Context, History, Piece
from closet_worker.recsys.scoring import weights
from closet_worker.text.templates import wish_reasons
from closet_worker.vision.embed import Embedder

from .context import JobContext
from .tag_item import BadJob, vision_for

MAX_IMAGE_BYTES = 10 * 1024 * 1024
OCCASIONS = ("office", "college", "party", "home")


def _fetch_image(url: str) -> Image.Image | None:
    """A hunt's product image. Pages and images are untrusted: size- and type-checked."""
    try:
        r = httpx.get(
            url, timeout=10, follow_redirects=True, headers={"User-Agent": "closet-personal/0.1"}
        )
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
            return None
        if len(r.content) > MAX_IMAGE_BYTES:
            return None
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except (httpx.HTTPError, OSError):
        return None


def embed_wish(wish: dict[str, Any], ctx: JobContext, emb: Embedder) -> tuple[list[float], str]:
    """Image if there is one (upload, then hunt image), else text. Returns (vector, kind)."""
    assert ctx.items is not None
    img = None
    if wish.get("photo_path"):
        img = Image.open(io.BytesIO(ctx.items.download(str(wish["photo_path"])))).convert("RGB")
    elif wish.get("image_url"):
        img = _fetch_image(str(wish["image_url"]))
    if img is not None:
        return [float(x) for x in emb.image([img])[0]], "image"
    color = (wish.get("color_name") or "").strip().lower()
    text = f"a photo of a {color} {wish.get('name', '')}".replace("  ", " ")
    return [float(x) for x in emb.text([text])[0]], "text"


def _month_spend(items: list[dict[str, Any]], month: str) -> int:
    return sum(
        int(i.get("price_cents") or 0)
        for i in items
        if str(i.get("bought_on") or "").startswith(month)
    )


def run_embed(
    payload: dict[str, Any], ctx: JobContext | None, emb: Embedder | None = None
) -> dict[str, Any]:
    if ctx is None or ctx.items is None:
        raise BadJob("no item store")
    wish = ctx.items.get_wish(str(payload.get("wish_id", "")))
    if wish is None:
        raise BadJob("That wishlist item no longer exists.")
    e = emb or vision_for(ctx.settings.embed_model, ctx.settings.device).emb
    vec, kind = embed_wish(wish, ctx, e)
    ctx.items.update_wish(str(wish["id"]), {"embedding": vec})
    return {"kind": kind, "model": e.model_id}


def run(
    payload: dict[str, Any], ctx: JobContext | None, emb: Embedder | None = None
) -> dict[str, Any]:
    if ctx is None or ctx.items is None:
        raise BadJob("no item store")
    wish = ctx.items.get_wish(str(payload.get("wish_id", "")))
    if wish is None:
        raise BadJob("That wishlist item no longer exists.")
    e = emb or vision_for(ctx.settings.embed_model, ctx.settings.device).emb
    vec, kind = embed_wish(wish, ctx, e)
    ctx.items.update_wish(str(wish["id"]), {"embedding": vec})

    rows = ctx.items.list_items()
    by_id = {str(r["id"]): r for r in rows}
    history = History.from_logs(ctx.items.list_wear_logs())
    profile = ctx.items.get_profile()
    tz = ZoneInfo(str(profile.get("timezone") or "America/New_York"))
    # The app sends today's date in your time zone; fall back to the Mac's clock in that zone.
    today = (
        date.fromisoformat(str(payload["date"])) if payload.get("date") else datetime.now(tz).date()
    )

    w = weights()
    tau = w["tau_image"] if kind == "image" else w["tau_text"]
    dupes = []
    for n in ctx.items.nearest_items(vec, wish.get("category"), 5):
        r = by_id.get(str(n["item_id"]))
        if r and r.get("status") != "retired" and float(n["similarity"]) >= tau:
            iid = str(r["id"])
            dupes.append(
                {
                    "id": iid,
                    "name": r["name"],
                    "similarity": round(float(n["similarity"]), 3),
                    "wears": history.piece_wears.get(iid, 0),
                }
            )

    pieces = [Piece.from_row(r) for r in rows]
    occasion = wish.get("occasion")
    new = Piece(
        id="wish",
        name=str(wish.get("name") or ""),
        category=str(wish.get("category") or ""),
        type=str(wish.get("name") or "").lower(),
        color_name=str(wish.get("color_name") or "").lower(),
        occasions=(occasion,) if occasion else OCCASIONS,
    )
    unlocks = sum(
        len(good_outfits_with(new, pieces, Context(occasion=o, day=today)))
        for o in ([occasion] if occasion else OCCASIONS)
    )
    budget = int(profile.get("monthly_budget_cents") or 0)
    spend = _month_spend(rows, today.isoformat()[:7])
    price = int(wish.get("price_cents") or 0)
    over_by = spend + price - budget if budget else 0
    v = verdict(any(d["wears"] > 0 for d in dupes), bool(dupes), unlocks, over_by > 0)
    result = {
        "verdict": v,
        "reasons": wish_reasons(dupes, unlocks, occasion, max(0, over_by), budget),
        "duplicates": dupes,
        "unlocks": unlocks,
        "month_spend_cents": spend,
        "over_budget_cents": max(0, over_by),
        "embedding_kind": kind,
        "model": e.model_id,
    }
    ctx.items.update_wish(
        str(wish["id"]), {"check_result": result, "checked_at": datetime.now(UTC).isoformat()}
    )
    return result

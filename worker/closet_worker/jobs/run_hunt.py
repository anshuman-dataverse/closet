"""`run_hunt` (SPEC 5.8, free path): writes the hunt's status, summary and top picks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from closet_worker.shopping import hunt as H
from closet_worker.shopping.fetch import Fetcher
from closet_worker.shopping.search import search

from .context import JobContext
from .tag_item import BadJob


def now() -> str:
    return datetime.now(UTC).isoformat()


def hunt_from(row: dict[str, Any], profile: dict[str, Any]) -> H.Hunt:
    analysis = profile.get("analysis") or {}
    return H.Hunt(
        query=str(row["query"]),
        budget_min_cents=row.get("budget_min_cents"),
        budget_max_cents=row.get("budget_max_cents"),
        occasion=row.get("occasion"),
        wears=profile.get("wears"),
        favorites=list(profile.get("favorite_stores") or []),
        best_colors=[str(c["name"]).lower() for c in analysis.get("best", [])][:3],
    )


def size_for(category_hint: str, sizes: dict[str, Any]) -> str | None:
    """Your size for the kind of thing hunted (tops, bottoms, shoes), if you've set it."""
    q = category_hint.lower()
    if any(w in q for w in ("shoe", "sneaker", "boot", "loafer")):
        return sizes.get("shoe") or None
    if any(w in q for w in ("jean", "chino", "trouser", "pant", "short")):
        w, i = sizes.get("waist"), sizes.get("inseam")
        return f"{w}x{i}" if w and i else (w or None)
    return sizes.get("top") or None


def rows_for(out: H.Outcome, query: str, sizes: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for rank, p in enumerate(out.picks, start=1):
        it = p.listing
        rows.append(
            {
                "rank": rank,
                "title": it.title[:200],
                "store": p.store,
                "url": it.url,
                "image_url": it.image_url,
                "price_cents": it.price_cents,
                "was_price_cents": it.was_price_cents,
                "rating": round(it.rating, 2) if it.rating is not None else None,
                "rating_count": it.rating_count,
                "why": H.why_text(p, H.Hunt(query, None, None)),
                "quality": H.quality_text(it),
                "size_available": H.size_available(it, size_for(query, sizes)),
            }
        )
    return rows


def run(payload: dict[str, Any], ctx: JobContext | None) -> dict[str, Any]:
    if ctx is None or ctx.items is None:
        raise BadJob("no item store")
    hunt_id = str(payload.get("hunt_id", ""))
    row = ctx.items.get_hunt(hunt_id)
    if row is None:
        raise BadJob("That hunt no longer exists.")
    ctx.items.update_hunt(hunt_id, {"status": "running", "started_at": now(), "error": None})
    profile = ctx.items.get_profile() or {}
    h = hunt_from(row, profile)
    fetcher = Fetcher()
    images = H.Images(fetcher)
    from closet_worker.vision.embed import load_embedder

    emb = load_embedder(ctx.settings.embed_model, ctx.settings.device)
    try:
        out = H.run_hunt(
            h,
            lambda q: search(ctx.settings.searxng_url, q),
            fetcher,
            H.clip_image_match(emb, images),
            H.palette_fit(profile.get("analysis"), images),
        )
    except Exception as e:
        ctx.items.update_hunt(
            hunt_id, {"status": "failed", "finished_at": now(), "error": str(e)[:300]}
        )
        raise
    rows = rows_for(out, h.query, dict(profile.get("sizes") or {}))
    ctx.items.replace_hunt_results(hunt_id, rows)
    ctx.items.update_hunt(
        hunt_id,
        {
            "status": "done",
            "finished_at": now(),
            "summary": out.summary,
            "pages_checked": out.pages_checked,
        },
    )
    return {"picks": len(rows), "summary": out.summary, "pages_checked": out.pages_checked}

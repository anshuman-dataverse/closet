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

    def hunt(
        sub: H.Hunt,
        max_queries: int = H.MAX_QUERIES,
        max_pages: int = H.MAX_PAGES,
        top_n: int = H.TOP_N,
    ) -> H.Outcome:
        return H.run_hunt(
            sub,
            lambda q: search(ctx.settings.searxng_url, q),
            fetcher,
            H.clip_image_match(emb, images),
            H.palette_fit(profile.get("analysis"), images),
            max_queries=max_queries,
            max_pages=max_pages,
            top_n=top_n,
        )

    if row.get("kind") == "look":
        return run_look(ctx, hunt_id, row, h, profile, hunt)
    try:
        out = hunt(h)
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


def pick_row(p: H.Pick, query: str, sizes: dict[str, Any], **extra: Any) -> dict[str, Any]:
    it = p.listing
    return {
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
        **extra,
    }


def run_look(
    ctx: JobContext,
    hunt_id: str,
    row: dict[str, Any],
    h: H.Hunt,
    profile: dict[str, Any],
    hunt: Any,
) -> dict[str, Any]:
    """Shop a look: one row per piece of each complete set (owned pieces included)."""
    from closet_worker.recsys.model import Piece
    from closet_worker.shopping.look import PER_SLOT, shop_look

    assert ctx.items is not None
    mode = str(row.get("look_mode") or "new")
    owned = [Piece.from_row(r) for r in ctx.items.list_items()] if mode == "own" else []
    sizes = dict(profile.get("sizes") or {})
    try:
        out = shop_look(
            h,
            mode,
            profile.get("analysis"),
            owned,
            lambda sub: hunt(sub, max_queries=7, max_pages=14, top_n=PER_SLOT),
        )
    except Exception as e:
        ctx.items.update_hunt(
            hunt_id, {"status": "failed", "finished_at": now(), "error": str(e)[:300]}
        )
        raise
    rows: list[dict[str, Any]] = []
    rank = 0
    slot_of = {s.category: s for s in out.slots}
    for n, ls in enumerate(out.sets, start=1):
        for cat in [s.category for s in out.slots]:
            rank += 1
            sl = slot_of[cat]
            if cat in ls.owned:
                piece = ls.owned[cat]
                rows.append(
                    {
                        "rank": rank,
                        "title": piece.name,
                        "owned_item_id": piece.id,
                        "slot": sl.label,
                        "set_no": n,
                        "why": "From your closet.",
                        "size_available": "unknown",
                    }
                )
            else:
                rows.append(
                    pick_row(ls.picks[cat], sl.query, sizes, rank=rank, slot=sl.label, set_no=n)
                )
    if not out.sets:  # no complete set: still show what was found, slot by slot
        for cat, picks in out.found.items():
            for p in picks:
                rank += 1
                rows.append(
                    pick_row(p, slot_of[cat].query, sizes, rank=rank, slot=slot_of[cat].label)
                )
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
    return {"sets": len(out.sets), "summary": out.summary, "pages_checked": out.pages_checked}

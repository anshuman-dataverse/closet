"""`rate_outfit` (Check my outfit): the pieces you picked, rated with every check, explained."""

from __future__ import annotations

from typing import Any

from closet_worker.recsys.model import Context, History, Piece
from closet_worker.recsys.rate import rate

from .context import JobContext
from .tag_item import BadJob


def run(payload: dict[str, Any], ctx: JobContext | None) -> dict[str, Any]:
    if ctx is None or ctx.items is None:
        raise BadJob("no item store")
    ids = [str(i) for i in payload.get("item_ids") or []]
    if len(ids) < 2:
        raise BadJob("Pick at least two pieces.")
    by_id = {str(r["id"]): r for r in ctx.items.list_items()}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise BadJob("Some of those pieces no longer exist.")
    pieces = [Piece.from_row(by_id[i]) for i in ids]
    c = Context.from_payload(payload)
    h = History.from_logs(ctx.items.list_wear_logs())
    analysis = (ctx.items.get_profile() or {}).get("analysis")
    return {**rate(pieces, c, h, analysis).to_json(), "item_ids": ids, "occasion": c.occasion}

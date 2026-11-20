"""`suggest_outfits` (SPEC 5.4): three diverse ideas, each logged as a `shown` suggestion event."""

from __future__ import annotations

import zlib
from typing import Any

from closet_worker.recsys.engine import ideas
from closet_worker.recsys.model import Context, History, Piece
from closet_worker.text.templates import render

from .context import JobContext
from .tag_item import BadJob

MODEL_VERSION = "rules-v1"


def run(payload: dict[str, Any], ctx: JobContext | None) -> dict[str, Any]:
    if ctx is None or ctx.items is None:
        raise BadJob("no item store")
    c = Context.from_payload(payload)
    pieces = [Piece.from_row(r) for r in ctx.items.list_items()]
    history = History.from_logs(ctx.items.list_wear_logs())
    picks = ideas(pieces, c, history)
    context = {"weather": payload.get("weather"), "note": c.note, "date": c.day.isoformat()}
    out = []
    for o, s in picks:
        ids = [p.id for p in o]
        out.append(
            {
                "item_ids": ids,
                "score": s.total,
                "terms": s.terms,
                "reasons": s.reasons,
                "text": render(s.reasons, seed=zlib.crc32("".join(ids).encode())),
            }
        )
    if out:
        event_ids = ctx.items.insert_events(
            [
                {
                    "occasion": c.occasion,
                    "item_ids": i["item_ids"],
                    "context": {**context, "terms": i["terms"]},
                    "score": i["score"],
                    "model_version": MODEL_VERSION,
                    "action": "shown",
                }
                for i in out
            ]
        )
        for i, eid in zip(out, event_ids, strict=False):
            i["event_id"] = eid
    return {"ideas": out, "model_version": MODEL_VERSION, "context": context}

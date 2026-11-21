"""`suggest_outfits` (SPEC 5.4): three diverse ideas, each logged as a `shown` suggestion event."""

from __future__ import annotations

import zlib
from typing import Any

from closet_worker.recsys import compat
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
    analysis = (ctx.items.get_profile() or {}).get("analysis")
    scorer = scorer_for(ctx)
    version = MODEL_VERSION if scorer is None else f"{MODEL_VERSION}+compat-{scorer.cfg.sha256[:8]}"
    picks = ideas(pieces, c, history, profile=analysis, compat=scorer)
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
                    "model_version": version,
                    "action": "shown",
                }
                for i in out
            ]
        )
        for i, eid in zip(out, event_ids, strict=False):
            i["event_id"] = eid
    return {"ideas": out, "model_version": version, "context": context}


def scorer_for(ctx: JobContext, *, require_gate: bool = True) -> compat.CompatScorer | None:
    """The outfit model, only when installed and (normally) only when its gate is open."""
    items = ctx.items
    assert items is not None

    def text() -> compat.TextEmbed:
        from closet_worker.vision.embed import load_embedder

        return load_embedder(compat.EMBEDDER, ctx.settings.device).text

    return compat.open_scorer(
        ctx.settings.compat_model_dir,
        lambda: items.list_embeddings(compat.EMBEDDER),
        text,
        require_gate=require_gate,
    )

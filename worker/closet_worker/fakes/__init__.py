"""`--fake` mode: no models. Jobs that need ML return fixtures; rule-only jobs run for real.

`tag_item` and `check_wish` write their fixtures to the database like the real handlers,
so the whole app flow runs in e2e tests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from closet_worker.jobs import analyze_profile, find_gaps, ping, suggest_outfits
from closet_worker.jobs.context import JobContext
from closet_worker.vision.style import build

FIXTURES = Path(__file__).parent


def _fixture(kind: str) -> dict[str, Any] | None:
    path = FIXTURES / f"{kind}.json"
    return json.loads(path.read_text()) if path.exists() else None


def run(kind: str, payload: dict[str, Any], ctx: JobContext | None = None) -> dict[str, Any]:
    if kind == "ping":
        return ping.run(payload)
    if kind == "suggest_outfits" and ctx and ctx.items:
        return suggest_outfits.run(payload, ctx)  # rules only: run the real thing
    if kind == "analyze_profile" and ctx and ctx.items:
        if payload.get("recompute"):
            return analyze_profile.run(
                payload, ctx
            )  # palette lookup and text only: run the real thing
        p = ctx.items.get_profile()
        overrides = {
            "undertone": p.get("undertone_override"),
            "contrast": p.get("contrast_override"),
        }
        analysis = build(_fixture("analyze_profile") or {}, overrides)
        ctx.items.update_profile(
            {"analysis": analysis, "analyzed_at": datetime.now(UTC).isoformat()}
        )
        return {"effective": analysis["effective"], "face_shape": analysis["face"].get("shape")}
    if kind == "find_gaps" and ctx and ctx.items:
        return find_gaps.run(payload, ctx)
    if kind == "tag_item":
        sug = _fixture("tag_item") or {}
        item_id = str(payload.get("item_id", ""))
        if ctx and ctx.items and ctx.items.get_item(item_id):
            ctx.items.update_item(
                item_id, {"suggestions": sug, "tags_status": sug.get("status", "ready")}
            )
        return {"suggestions": sug, "cutout_path": None, "photo_path": payload.get("photo_path")}
    if kind == "check_wish":
        res = _fixture("check_wish") or {}
        wish_id = str(payload.get("wish_id", ""))
        if ctx and ctx.items and ctx.items.get_wish(wish_id):
            ctx.items.update_wish(
                wish_id, {"check_result": res, "checked_at": datetime.now(UTC).isoformat()}
            )
        return res
    return _fixture(kind) or {"fake": True, "kind": kind}

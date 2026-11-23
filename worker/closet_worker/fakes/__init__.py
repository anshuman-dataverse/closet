"""`--fake` mode: no models. Jobs that need ML return fixtures; rule-only jobs run for real.

`tag_item` and `check_wish` write their fixtures to the database like the real handlers, and
`read_label` parses fixed label text, so the whole app flow runs in e2e tests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from closet_worker.jobs import analyze_profile, find_gaps, ping, read_label, suggest_outfits
from closet_worker.jobs.context import JobContext
from closet_worker.vision.label import Line
from closet_worker.vision.style import build


class FixtureLabelReader:
    """Fixed label text instead of Apple's text recognition; the real parser still runs."""

    LINES = ("W32 L30", "Relaxed fit", "98% Cotton 2% Elastane", "Machine wash cold")

    def read(self, image: bytes) -> list[Line]:
        return [Line("Levi's", 0.99, 0.15), *(Line(t, 0.95, 0.05) for t in self.LINES)]


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
    if kind == "run_hunt" and ctx and ctx.items:
        hunt_id = str(payload.get("hunt_id", ""))
        row = ctx.items.get_hunt(hunt_id)
        fx = _fixture("run_look" if row and row.get("kind") == "look" else "run_hunt") or {}
        if row:
            ctx.items.replace_hunt_results(hunt_id, fx.get("picks", []))
            ctx.items.update_hunt(
                hunt_id,
                {
                    "status": "done",
                    "summary": fx.get("summary"),
                    "pages_checked": fx.get("pages_checked", 0),
                    "finished_at": datetime.now(UTC).isoformat(),
                },
            )
        return {"picks": len(fx.get("picks", [])), "summary": fx.get("summary")}
    if kind == "price_check":
        return {"checked": 0, "priced": 0}  # no network in fake mode
    if kind == "read_label" and ctx and ctx.items:
        return read_label.run(payload, ctx, FixtureLabelReader())
    if kind == "check_wish":
        res = _fixture("check_wish") or {}
        wish_id = str(payload.get("wish_id", ""))
        if ctx and ctx.items and ctx.items.get_wish(wish_id):
            ctx.items.update_wish(
                wish_id, {"check_result": res, "checked_at": datetime.now(UTC).isoformat()}
            )
        return res
    return _fixture(kind) or {"fake": True, "kind": kind}

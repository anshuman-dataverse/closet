"""`--fake` mode: every job kind returns a fixture right away (for e2e tests and UI work).

`tag_item` also writes its fixture to the item, like the real handler, so the whole app flow runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from closet_worker.jobs import ping
from closet_worker.jobs.context import JobContext

FIXTURES = Path(__file__).parent


def _fixture(kind: str) -> dict[str, Any] | None:
    path = FIXTURES / f"{kind}.json"
    return json.loads(path.read_text()) if path.exists() else None


def run(kind: str, payload: dict[str, Any], ctx: JobContext | None = None) -> dict[str, Any]:
    if kind == "ping":
        return ping.run(payload)
    if kind == "tag_item":
        sug = _fixture("tag_item") or {}
        item_id = str(payload.get("item_id", ""))
        if ctx and ctx.items and ctx.items.get_item(item_id):
            ctx.items.update_item(
                item_id, {"suggestions": sug, "tags_status": sug.get("status", "ready")}
            )
        return {"suggestions": sug, "cutout_path": None, "photo_path": payload.get("photo_path")}
    return _fixture(kind) or {"fake": True, "kind": kind}

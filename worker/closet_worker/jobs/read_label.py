"""`read_label`: read the piece's label photo on this Mac (brand, size, materials, fit).

Writes `items.suggestions.label` and returns the same. Never changes the piece's own fields: the
app fills only fields you haven't touched, and you can change anything it fills.
"""

from __future__ import annotations

from typing import Any

from closet_worker.vision.label import AppleVisionReader, TextReader, parse

from .context import JobContext
from .tag_item import BadJob


def run(
    payload: dict[str, Any], ctx: JobContext | None, reader: TextReader | None = None
) -> dict[str, Any]:
    if ctx is None or ctx.items is None:
        raise BadJob("no item store")
    item_id = str(payload.get("item_id", ""))
    item = ctx.items.get_item(item_id)
    if item is None:
        raise BadJob("That piece no longer exists.")
    path = str(payload.get("label_path") or item.get("label_path") or "")
    if not path:
        raise BadJob("That piece has no label photo yet.")
    if not path.startswith(f"{ctx.items.owner}/items/{item_id}/") or not path.endswith(".jpg"):
        raise BadJob("That label photo isn’t this piece’s.")
    lines = (reader or AppleVisionReader()).read(ctx.items.download(path))
    read = parse(lines).to_json()
    if not read["lines"]:
        read["notes"].append("no text found: take the label straight on, close up, in good light")
    read["label_path"] = path
    sug = dict(item.get("suggestions") or {})
    sug["label"] = read
    ctx.items.update_item(item_id, {"suggestions": sug})
    return {"label": read}

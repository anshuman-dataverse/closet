"""`closet-worker export-eval`: photos + a prefilled labels.csv + the eval code, zipped for Colab.

Labels come from what you entered in the app, so you only check and fix them.
Photos are the app's re-encoded uploads, so they carry no EXIF or location data.
"""

from __future__ import annotations

import csv
import zipfile
from pathlib import Path

from .store import ItemStore

WORKER_DIR = Path(__file__).resolve().parent.parent
CODE = [
    "closet_worker/__init__.py",
    "closet_worker/vision",
    "closet_worker/vocab",
    "eval/__init__.py",
    "eval/tagging.py",
]


def export_eval(items: ItemStore, out: str) -> Path:
    root = Path(out).expanduser()
    photos = root / "photos"
    photos.mkdir(parents=True, exist_ok=True)
    rows = []
    for n, it in enumerate([i for i in items.list_items() if i.get("photo_path")], start=1):
        name = f"{n:03d}.jpg"
        (photos / name).write_bytes(items.download(str(it["photo_path"])))
        rows.append(
            {
                "file": name,
                "item_name": it.get("name") or "",
                "category": it.get("category") or "",
                "type": (it.get("type") or "").lower(),
                "pattern": it.get("pattern") or "",
                "color": (it.get("color_name") or "").lower(),
            }
        )
    labels = root / "labels.csv"
    if not labels.exists():  # never overwrite labels you've already corrected
        with labels.open("w", newline="") as f:
            w = csv.DictWriter(
                f, fieldnames=["file", "item_name", "category", "type", "pattern", "color"]
            )
            w.writeheader()
            w.writerows(rows)

    zip_path = root / "closet-eval.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(labels, "labels.csv")
        for p in sorted(photos.glob("*.jpg")):
            z.write(p, f"photos/{p.name}")
        for rel in CODE:
            src = WORKER_DIR / rel
            for path in [src] if src.is_file() else sorted(src.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    z.write(path, f"code/{path.relative_to(WORKER_DIR)}")
    return zip_path

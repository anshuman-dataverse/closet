from __future__ import annotations

from dataclasses import dataclass

from closet_worker.config import Settings
from closet_worker.store import ItemStore


@dataclass
class JobContext:
    settings: Settings
    items: ItemStore | None = None

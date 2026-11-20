"""Typed inputs for the recommender, built from database rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from functools import cache
from typing import Any

import numpy as np
from numpy.typing import NDArray

from closet_worker.vision.color import hex_to_rgb, srgb_to_lab
from closet_worker.vocab import load_vocab

WARMTH_LEVEL = {"light": 0, "medium": 1, "warm": 2}


@cache
def _named_lab(name: str) -> tuple[float, float, float] | None:
    hx = load_vocab().colors.get(name.strip().lower())
    if not hx:
        return None
    lab = srgb_to_lab(np.array([hex_to_rgb(hx)]))[0]
    return float(lab[0]), float(lab[1]), float(lab[2])


@dataclass(frozen=True)
class Piece:
    id: str
    name: str
    category: str
    type: str = ""
    color_name: str = ""
    color_hex: str | None = None
    formality: int | None = None
    warmth: str | None = None
    occasions: tuple[str, ...] = ()
    status: str = "active"

    @staticmethod
    def from_row(r: dict[str, Any]) -> Piece:
        return Piece(
            id=str(r["id"]),
            name=str(r.get("name") or ""),
            category=str(r.get("category") or ""),
            type=str(r.get("type") or "").lower(),
            color_name=str(r.get("color_name") or "").lower(),
            color_hex=r.get("color_hex"),
            formality=r.get("formality"),
            warmth=r.get("warmth"),
            occasions=tuple(r.get("occasions") or ()),
            status=str(r.get("status") or "active"),
        )

    @property
    def lab(self) -> tuple[float, float, float] | None:
        if self.color_hex:
            lab: NDArray[np.float64] = srgb_to_lab(np.array([hex_to_rgb(self.color_hex)]))[0]
            return float(lab[0]), float(lab[1]), float(lab[2])
        return _named_lab(self.color_name) if self.color_name else None

    @property
    def noun(self) -> str:
        """'shirt' for 'oxford shirt'; falls back to the name."""
        t = self.type.strip()
        return t.split()[-1] if t else self.name.lower()


@dataclass(frozen=True)
class Context:
    occasion: str
    day: date
    temp_high_f: float | None = None
    rain_pct: float = 0.0
    note: str = ""
    unit: str = "F"  # how to show temperatures in text
    code: int | None = None  # Open-Meteo weather code (0–2 is clear to partly cloudy)

    @staticmethod
    def from_payload(p: dict[str, Any]) -> Context:
        w = p.get("weather") or {}
        unit = str(w.get("unit") or "F").upper()
        high = w.get("high")
        high_f = (
            None if high is None else (float(high) * 9 / 5 + 32 if unit == "C" else float(high))
        )
        return Context(
            occasion=str(p.get("occasion") or "office"),
            day=date.fromisoformat(str(p.get("date") or date.today().isoformat())),
            temp_high_f=high_f,
            rain_pct=float(w.get("rain_pct") or 0),
            note=str(p.get("note") or "")[:200],
            unit=unit,
            code=None if w.get("code") is None else int(w["code"]),
        )

    def temp_text(self) -> str:
        if self.temp_high_f is None:
            return ""
        t = (self.temp_high_f - 32) * 5 / 9 if self.unit == "C" else self.temp_high_f
        return f"{round(t)}°{self.unit}"


@dataclass
class History:
    """When each piece and each exact set of pieces was last worn."""

    piece_last: dict[str, date] = field(default_factory=dict)
    outfit_last: dict[frozenset[str], date] = field(default_factory=dict)
    piece_wears: dict[str, int] = field(default_factory=dict)

    @staticmethod
    def from_logs(logs: list[dict[str, Any]]) -> History:
        h = History()
        for log in logs:
            d = date.fromisoformat(str(log["worn_on"]))
            ids = frozenset(str(i) for i in log.get("item_ids") or [])
            for i in ids:
                h.piece_wears[i] = h.piece_wears.get(i, 0) + 1
                if i not in h.piece_last or d > h.piece_last[i]:
                    h.piece_last[i] = d
            if ids and (ids not in h.outfit_last or d > h.outfit_last[ids]):
                h.outfit_last[ids] = d
        return h

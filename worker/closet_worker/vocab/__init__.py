"""Tagging vocabularies (types, colors, patterns), loaded from the YAML files next to this."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).parent
CATEGORIES = ("Tops", "Bottoms", "Layers", "Shoes", "Accessories", "Sets & suits")
OCCASIONS = ("office", "college", "party", "home")
WARMTH = ("light", "medium", "warm")


@dataclass(frozen=True)
class TypeEntry:
    type: str
    category: str
    formality: int
    warmth: str
    occasions: tuple[str, ...]
    prompt: str | None = None


@dataclass(frozen=True)
class Vocab:
    types: tuple[TypeEntry, ...]
    colors: dict[str, str]  # name -> "#rrggbb"
    patterns: dict[str, str]  # name -> prompt


def _load(name: str) -> Any:
    return yaml.safe_load((HERE / name).read_text())


@cache
def load_vocab() -> Vocab:
    types = tuple(
        TypeEntry(
            type=str(t["type"]),
            category=str(t["category"]),
            formality=int(t["formality"]),
            warmth=str(t["warmth"]),
            occasions=tuple(t["occasions"]),
            prompt=t.get("prompt"),
        )
        for t in _load("types.yaml")
    )
    colors = {str(k): str(v).lower() for k, v in _load("colors.yaml").items()}
    patterns = {str(k): str(v) for k, v in _load("patterns.yaml").items()}
    return Vocab(types=types, colors=colors, patterns=patterns)

"""The store list (vocab/stores.yaml): which URLs are product pages, and from which store."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from urllib.parse import urlsplit

import yaml

STORES_FILE = Path(__file__).resolve().parent.parent / "vocab" / "stores.yaml"


@dataclass(frozen=True)
class Store:
    name: str
    domains: tuple[str, ...]
    product: re.Pattern[str]
    example: str
    checked: str = "unknown"


@dataclass(frozen=True)
class StoreList:
    stores: tuple[Store, ...]
    exclude: re.Pattern[str]

    def by_host(self, host: str) -> Store | None:
        h = host.lower()
        return next((s for s in self.stores if h in s.domains), None)

    def product_store(self, url: str) -> Store | None:
        """The store if `url` is a product page on a listed store (not a kids' page), else None."""
        u = urlsplit(url)
        if u.scheme not in ("http", "https") or not u.hostname:
            return None
        s = self.by_host(u.hostname)
        if s is None:
            return None
        path = u.path + (f"?{u.query}" if u.query else "")
        if self.exclude.search(u.path) or not s.product.search(path):
            return None
        return s

    def match_names(self, names: list[str]) -> list[Store]:
        """Favorite stores typed in Settings ("J.Crew", "uniqlo") → listed stores."""

        def key(x: str) -> str:
            return re.sub(r"[^a-z0-9]", "", x.lower())

        want = {key(n) for n in names if n.strip()}
        return [
            s
            for s in self.stores
            if key(s.name) in want or any(key(d.split(".")[-2]) in want for d in s.domains)
        ]


@cache
def load_stores(path: Path = STORES_FILE) -> StoreList:
    d = yaml.safe_load(path.read_text())
    return StoreList(
        tuple(
            Store(
                s["name"],
                tuple(s["domains"]),
                re.compile(s["product"]),
                s["example"],
                str(s.get("checked") or "unknown"),
            )
            for s in d["stores"]
        ),
        re.compile(d["exclude"]),
    )


def canonical(url: str) -> str:
    """Same product, different tracking parameters → one URL (Gap keeps its pid)."""
    u = urlsplit(url)
    keep = ""
    if u.query:
        m = re.search(r"(?:^|&)(pid=\d+)", u.query) or re.search(r"(?:^|&)(page=[^&]+)", u.query)
        keep = m.group(1) if m else ""
    return f"{u.scheme}://{u.hostname}{u.path}" + (f"?{keep}" if keep else "")

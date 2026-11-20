"""Color: k-means in CIELAB over the piece's pixels, named by ΔE2000 (SPEC 5.1 step 6)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from skimage.color import deltaE_ciede2000, rgb2lab
from sklearn.cluster import KMeans

SECONDARY_MIN_SHARE = 0.20
MAX_SAMPLES = 20_000


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb: NDArray[np.floating] | tuple[float, float, float]) -> str:
    r, g, b = (round(float(np.clip(c, 0, 255))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def srgb_to_lab(rgb: NDArray[np.integer] | NDArray[np.floating]) -> NDArray[np.float64]:
    """(N, 3) sRGB 0–255 → (N, 3) CIELAB (D65)."""
    a = np.asarray(rgb, dtype=np.float64).reshape(-1, 1, 3) / 255.0
    return np.asarray(rgb2lab(a), dtype=np.float64).reshape(-1, 3)


def delta_e(lab1: NDArray[np.float64], lab2: NDArray[np.float64]) -> NDArray[np.float64]:
    return np.asarray(deltaE_ciede2000(lab1, lab2), dtype=np.float64)


@dataclass(frozen=True)
class Palette:
    names: tuple[str, ...]
    hexes: tuple[str, ...]
    labs: NDArray[np.float64]

    @staticmethod
    def from_dict(colors: dict[str, str]) -> Palette:
        names = tuple(colors)
        hexes = tuple(colors[n] for n in names)
        labs = srgb_to_lab(np.array([hex_to_rgb(h) for h in hexes]))
        return Palette(names, hexes, labs)

    def nearest(self, lab: NDArray[np.float64]) -> tuple[str, float]:
        d = delta_e(np.repeat(lab.reshape(1, 3), len(self.names), axis=0), self.labs)
        k = int(np.argmin(d))
        return self.names[k], float(d[k])


@dataclass(frozen=True)
class ColorShare:
    name: str
    hex: str  # the cluster's actual color, not the palette's
    share: float


def dominant_colors(
    rgb: NDArray[np.uint8],
    mask: NDArray[np.bool_] | None,
    palette: Palette,
    k: int = 3,
    seed: int = 0,
) -> list[ColorShare]:
    """Named colors of the masked pixels, largest share first. Clusters with the same name merge."""
    px = rgb.reshape(-1, 3) if mask is None else rgb[mask.astype(bool)]
    if len(px) == 0:
        px = rgb.reshape(-1, 3)
    rng = np.random.default_rng(seed)
    if len(px) > MAX_SAMPLES:  # k-means on a sample is plenty for 3 clusters
        px = px[rng.choice(len(px), MAX_SAMPLES, replace=False)]
    lab = srgb_to_lab(px)
    n = int(min(k, len(np.unique(px, axis=0))))
    km = KMeans(n_clusters=max(1, n), n_init=4, random_state=seed).fit(lab)
    counts = np.bincount(km.labels_, minlength=km.n_clusters).astype(np.float64)
    shares = counts / counts.sum()
    # Group clusters by color name: shares add up; the hex is the biggest cluster's mean color.
    groups: dict[str, tuple[float, float, str]] = {}  # name -> (total share, biggest share, hex)
    for c in range(km.n_clusters):
        name, _ = palette.nearest(km.cluster_centers_[c])
        hx = rgb_to_hex(tuple(px[km.labels_ == c].mean(axis=0)))
        total, biggest, cur_hex = groups.get(name, (0.0, -1.0, hx))
        groups[name] = (
            total + shares[c],
            max(biggest, shares[c]),
            hx if shares[c] > biggest else cur_hex,
        )
    out = [ColorShare(name, hx, float(total)) for name, (total, _, hx) in groups.items()]
    return sorted(out, key=lambda c: c.share, reverse=True)


def primary_secondary(shares: list[ColorShare]) -> tuple[ColorShare, ColorShare | None]:
    primary = shares[0]
    second = shares[1] if len(shares) > 1 and shares[1].share >= SECONDARY_MIN_SHARE else None
    return primary, second

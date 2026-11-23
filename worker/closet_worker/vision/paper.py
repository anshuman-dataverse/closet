"""White-paper reference (von Kries): find a plain white sheet held beside the face and scale each
linear RGB channel so it reads neutral, removing the light's color cast before skin is read.

A port of web/lib/style/calibrate.ts (findPaper), kept identical so the Mac and the /colors page
agree; tests/test_paper.py checks the same cases as the web.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .color import srgb_to_lab

MIN_L = 70.0  # brighter than a typical wall; white paper in daylight reads ~80–95
MAX_CHROMA = 22.0
CLIP = 250.0

Box = tuple[float, float, float, float]  # x0, y0, x1, y1


@dataclass(frozen=True)
class Paper:
    gains: tuple[float, float, float]
    cast: float  # the paper's own chroma before correction
    cells: int
    box: Box


@dataclass(frozen=True)
class PaperResult:
    paper: Paper | None
    problem: str | None


def _round(x: float) -> int:
    return math.floor(x + 0.5)  # JavaScript's Math.round, for positive numbers


def to_linear(c8: NDArray[np.float64]) -> NDArray[np.float64]:
    c = c8 / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def from_linear(lin: NDArray[np.float64]) -> NDArray[np.float64]:
    c = np.where(
        lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(np.maximum(lin, 0), 1 / 2.4) - 0.055
    )
    return np.clip(np.floor(c * 255 + 0.5), 0, 255)


@dataclass
class _Grid:
    size: int
    cols: int
    rows: int
    mean: NDArray[np.float64]  # (cells, 3) sRGB means
    lab: NDArray[np.float64]  # (cells, 3)


def _grid(rgb: NDArray[np.uint8]) -> _Grid:
    h, w = rgb.shape[:2]
    size = max(4, _round(min(w, h) / 80))
    cols, rows = w // size, h // size
    cells = rgb[: rows * size, : cols * size].astype(np.float64)
    mean = cells.reshape(rows, size, cols, size, 3).mean(axis=(1, 3)).reshape(-1, 3)
    return _Grid(size, cols, rows, mean, srgb_to_lab(mean))


def _components(g: _Grid, ok: NDArray[np.bool_]) -> list[list[int]]:
    """4-connected groups of cells, in the same visiting order as the web port."""
    seen = np.zeros(g.cols * g.rows, dtype=bool)
    out: list[list[int]] = []
    for s in range(g.cols * g.rows):
        if seen[s] or not ok[s]:
            continue
        comp: list[int] = []
        stack = [s]
        seen[s] = True
        while stack:
            i = stack.pop()
            comp.append(i)
            r, c = divmod(i, g.cols)
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                rr, cc = r + dr, c + dc
                if rr < 0 or cc < 0 or rr >= g.rows or cc >= g.cols:
                    continue
                j = rr * g.cols + cc
                if not seen[j] and ok[j]:
                    seen[j] = True
                    stack.append(j)
        out.append(comp)
    return out


def sheet_like(cols: int, rows: int, comp: list[int], face: tuple[float, float], cell: int) -> bool:
    """Shaped like a sheet held beside the face (not sky, a wall or a window)?"""
    rs = [i // cols for i in comp]
    cs = [i % cols for i in comp]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    w, h = c1 - c0 + 1, r1 - r0 + 1
    fill = len(comp) / (w * h)
    aspect = w / h
    edges = sum((r0 == 0, c0 == 0, r1 == rows - 1, c1 == cols - 1))
    share = len(comp) / (cols * rows)
    y0, y1 = r0 * cell, (r1 + 1) * cell
    overlap = max(0.0, min(y1, face[1]) - max(y0, face[0])) / max(1, y1 - y0)
    return (
        fill >= 0.7
        and 0.25 <= aspect <= 4
        and r0 != 0
        and edges <= 1
        and share <= 0.2
        and overlap >= 0.3
    )


def _to_paper(g: _Grid, comp: list[int]) -> Paper:
    lin = to_linear(g.mean[comp]).mean(axis=0)
    y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    gains = tuple(float(y / max(c, 1e-6)) for c in lin)
    lab = srgb_to_lab(from_linear(lin).reshape(1, 3))[0]
    rows = [i // g.cols for i in comp]
    cols = [i % g.cols for i in comp]
    box = (
        float(min(cols) * g.size),
        float(min(rows) * g.size),
        float((max(cols) + 1) * g.size),
        float((max(rows) + 1) * g.size),
    )
    return Paper(gains, float(math.hypot(lab[1], lab[2])), len(comp), box)  # type: ignore[arg-type]


def find_paper(rgb: NDArray[np.uint8], face: Box) -> PaperResult:
    """The largest bright, low-saturation, sheet-shaped area outside the face."""
    g = _grid(rgb)
    fx0, fy0, fx1, fy1 = face
    pad = 0.1 * (fx1 - fx0)
    idx = np.arange(g.cols * g.rows)
    cx = (idx % g.cols + 0.5) * g.size
    cy = (idx // g.cols + 0.5) * g.size
    outside = (cx < fx0 - pad) | (cx > fx1 + pad) | (cy < fy0 - pad) | (cy > fy1 + pad)
    chroma = np.hypot(g.lab[:, 1], g.lab[:, 2])
    white = outside & (g.lab[:, 0] >= MIN_L) & (chroma <= MAX_CHROMA)
    mx = g.mean.max(axis=1)
    min_cells = max(12, _round(0.015 * g.cols * g.rows))
    sheets = sorted(
        (
            c
            for c in _components(g, white & (mx < CLIP))
            if len(c) >= min_cells and sheet_like(g.cols, g.rows, c, (fy0, fy1), g.size)
        ),
        key=len,
        reverse=True,
    )
    if sheets:
        return PaperResult(_to_paper(g, sheets[0]), None)
    clipped = max(_components(g, white & (mx >= CLIP)), key=len, default=[])
    if len(clipped) >= min_cells:
        return PaperResult(
            None, "The paper is too bright to read. Tilt it a little away from the light."
        )
    return PaperResult(
        None, "No white paper found. Hold a plain white sheet beside your face, or tap it."
    )


def apply_gains(rgb: NDArray[np.uint8], gains: tuple[float, float, float]) -> NDArray[np.uint8]:
    """A corrected copy (sRGB in, sRGB out), through a lookup table per channel."""
    v = np.arange(256, dtype=np.float64)
    out = np.empty_like(rgb)
    for ch in range(3):
        lut = from_linear(np.minimum(1.0, to_linear(v) * gains[ch])).astype(np.uint8)
        out[..., ch] = lut[rgb[..., ch]]
    return out


def face_box(pts: list[tuple[float, float]]) -> Box:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))

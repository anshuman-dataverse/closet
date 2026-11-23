"""Skin, hair and lighting reads from Face Mesh landmarks (SPEC 5.2 steps 1–4). Pure functions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from numpy.typing import NDArray

from .color import srgb_to_lab

Point = tuple[float, float]  # pixel coordinates
# Face Mesh indices: sample both cheeks and the mid-forehead, away from eyes, brows and lips.
CHEEK_L, CHEEK_R, FOREHEAD = 50, 280, 151
# Every spot skin is read from (cheeks, under the eyes, cheekbones, lower cheeks, mid-forehead).
# Spots that don't look like the rest (a cap's shadow, glasses, a sheet of paper, a beard) are
# dropped, so one bad spot can't swing the read. Same list in web/lib/style/skin.ts.
SPOTS: dict[str, int] = {
    "cheek_l": 50,
    "cheek_r": 280,
    "under_eye_l": 101,
    "under_eye_r": 330,
    "cheekbone_l": 117,
    "cheekbone_r": 346,
    "low_cheek_l": 205,
    "low_cheek_r": 425,
    "forehead": 151,
}
TOP, CHIN, LEFT, RIGHT = 10, 152, 234, 454  # face extremes


@cache
def thresholds() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(
        (Path(__file__).parent.parent / "vocab" / "style.yaml").read_text()
    )
    return data


def _disk(rgb: NDArray[np.uint8], c: Point, r: float) -> NDArray[np.uint8]:
    h, w = rgb.shape[:2]
    ys, xs = np.ogrid[:h, :w]
    m = (xs - c[0]) ** 2 + (ys - c[1]) ** 2 <= r * r
    return rgb[m]


def face_width(pts: list[Point]) -> float:
    return math.dist(pts[LEFT], pts[RIGHT])


@dataclass
class SkinRead:
    lab: tuple[float, float, float]  # median skin L*, a*, b*
    hair_L: float | None
    face_pixels: NDArray[np.uint8]
    dropped: tuple[str, ...] = ()  # spots left out (they didn't look like the rest)


def sample_spots(
    rgb: NDArray[np.uint8], pts: list[Point], t: dict[str, Any] | None = None
) -> tuple[NDArray[np.uint8], tuple[str, ...]]:
    """Skin pixels from the spots that agree with each other, and the names of those dropped."""
    st = (t or thresholds())["skin_sample"]
    r = max(3.0, 0.04 * face_width(pts))
    meds: dict[str, NDArray[np.float64]] = {}
    pix: dict[str, NDArray[np.uint8]] = {}
    for name, i in SPOTS.items():
        px = _disk(rgb, pts[i], r)
        if len(px) == 0:
            continue
        lab = srgb_to_lab(px)
        chroma = np.hypot(lab[:, 1], lab[:, 2])
        paper = (lab[:, 0] > st["paper_L"]) & (chroma < st["paper_chroma"])
        ok = ~(paper | (lab[:, 0] < st["dark_L"]))
        if ok.mean() < st["min_skin_share"]:
            continue
        meds[name] = np.median(lab[ok], axis=0)
        pix[name] = px[ok]
    if not meds:  # nothing looked like skin: fall back to the three classic spots, unfiltered
        px = np.concatenate([_disk(rgb, pts[i], r) for i in (CHEEK_L, CHEEK_R, FOREHEAD)])
        return px, tuple(SPOTS)
    centre = np.median(np.array(list(meds.values())), axis=0)
    keep = [n for n, m in meds.items() if float(np.linalg.norm(m - centre)) <= st["max_delta_e"]]
    if len(keep) < 2:
        keep = list(meds)
    dropped = tuple(n for n in SPOTS if n not in keep)
    return np.concatenate([pix[n] for n in keep]), dropped


def read_skin(rgb: NDArray[np.uint8], pts: list[Point]) -> SkinRead:
    px, dropped = sample_spots(rgb, pts)
    lab = np.median(srgb_to_lab(px), axis=0)
    # Hair: a band above the top of the mesh, between the temples.
    top, fh = pts[TOP], math.dist(pts[TOP], pts[CHIN])
    x0, x1 = sorted(
        (
            pts[LEFT][0] + 0.25 * (pts[RIGHT][0] - pts[LEFT][0]),
            pts[RIGHT][0] - 0.25 * (pts[RIGHT][0] - pts[LEFT][0]),
        )
    )
    y0, y1 = int(max(0, top[1] - 0.22 * fh)), int(max(0, top[1] - 0.08 * fh))
    band = rgb[y0:y1, int(max(0, x0)) : int(max(0, x1))].reshape(-1, 3)
    hair_L = float(np.median(srgb_to_lab(band)[:, 0])) if len(band) >= 20 else None
    return SkinRead((float(lab[0]), float(lab[1]), float(lab[2])), hair_L, px, dropped)


def hue_deg(lab: tuple[float, float, float]) -> float:
    return math.degrees(math.atan2(lab[2], lab[1]))


def ita_deg(lab: tuple[float, float, float]) -> float:
    return math.degrees(math.atan2(lab[0] - 50.0, max(lab[2], 1e-6)))


def undertone(lab: tuple[float, float, float], t: dict[str, Any] | None = None) -> str:
    u = (t or thresholds())["undertone"]
    _, a, b = lab
    if a <= u["olive_max_a"] and u["olive_b"][0] <= b <= u["olive_b"][1]:
        return "olive"
    h = hue_deg(lab)
    if h >= u["warm_min_hue"]:
        return "warm"
    if h <= u["cool_max_hue"]:
        return "cool"
    return "neutral"


def depth(lab: tuple[float, float, float], t: dict[str, Any] | None = None) -> str:
    d = (t or thresholds())["depth"]
    ita = ita_deg(lab)
    return "light" if ita > d["light_min_ita"] else "deep" if ita < d["deep_max_ita"] else "medium"


def contrast(skin_L: float, hair_L: float | None, t: dict[str, Any] | None = None) -> str | None:
    if hair_L is None:
        return None
    c = (t or thresholds())["contrast"]
    delta = abs(skin_L - hair_L)
    return "low" if delta < c["low_below"] else "high" if delta > c["high_above"] else "medium"


def lighting_note(
    rgb: NDArray[np.uint8],
    face_px: NDArray[np.uint8],
    t: dict[str, Any] | None = None,
    calibrated: bool = False,
) -> str | None:
    """A retake hint when the face is dark, the light has a strong color cast, or highlights are
    blown. A photo corrected with white paper has no cast left to warn about."""
    li = (t or thresholds())["lighting"]
    face_lab = srgb_to_lab(face_px)
    small = rgb[:: max(1, rgb.shape[0] // 200), :: max(1, rgb.shape[1] // 200)].reshape(-1, 3)
    world = srgb_to_lab(small).mean(axis=0)
    dark = float(np.median(face_lab[:, 0])) < li["dark_face_L"]
    warm = not calibrated and (world[2] > li["warm_cast_b"] or world[1] > li["cast_a"])
    cool = not calibrated and world[2] < li["cool_cast_b"]
    blown = float((face_px.max(axis=1) >= 250).mean()) > li["blown_share"]
    if dark and warm:
        return "Lighting looks warm and dim. Retake near a window for a better read."
    if dark:
        return "The photo is quite dark. Retake near a window in daylight for a better read."
    if warm:
        return "Lighting looks warm, which can shift the read. Retake in daylight, away from lamps."
    if cool:
        return "Lighting looks cool or blue. Retake in daylight for a better read."
    if blown:
        return "Some of your face is overexposed. Retake out of direct sun for a better read."
    return None

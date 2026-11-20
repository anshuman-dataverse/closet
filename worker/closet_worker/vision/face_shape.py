"""Face shape from Face Mesh proportions, for frame and hairstyle tips. A guideline, not a rule."""

from __future__ import annotations

import math
from typing import Any

from .skin import CHIN, LEFT, RIGHT, TOP, Point, thresholds

NOSE = 1
JAW_L, JAW_R = 172, 397
FOREHEAD_L, FOREHEAD_R = 103, 332


def ratios(pts: list[Point]) -> dict[str, float]:
    cheek = math.dist(pts[LEFT], pts[RIGHT])
    mid_x = (pts[LEFT][0] + pts[RIGHT][0]) / 2
    return {
        "length": math.dist(pts[TOP], pts[CHIN]) / cheek,
        "jaw": math.dist(pts[JAW_L], pts[JAW_R]) / cheek,
        "forehead": math.dist(pts[FOREHEAD_L], pts[FOREHEAD_R]) / cheek,
        "yaw": abs(pts[NOSE][0] - mid_x) / cheek,
    }


def classify(r: dict[str, float], t: dict[str, Any] | None = None) -> str | None:
    """oval, round, square, oblong, heart or diamond; None when the face is turned too far."""
    f = (t or thresholds())["face_shape"]
    if r["yaw"] > f["max_yaw"]:
        return None
    if r["length"] >= f["oblong_min_length"]:
        return "oblong"
    if r["length"] < f["round_max_length"] and r["jaw"] >= f["round_jaw"]:
        return "round"
    if r["length"] < f["square_max_length"] and r["jaw"] >= f["wide_jaw"]:
        return "square"
    if r["forehead"] >= f["wide_forehead"] and r["jaw"] < f["narrow_jaw"]:
        return "heart"
    if r["forehead"] < f["narrow_forehead"] and r["jaw"] < f["narrow_jaw"]:
        return "diamond"
    return "oval"

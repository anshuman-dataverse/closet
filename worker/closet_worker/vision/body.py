"""Body proportions from Pose landmarks (SPEC 5.2 step 6). Neutral, practical fit notes only."""

from __future__ import annotations

import math
from typing import Any

from .skin import thresholds

SH_L, SH_R, HIP_L, HIP_R, ANK_L, ANK_R = 11, 12, 23, 24, 27, 28
NEEDED = (SH_L, SH_R, HIP_L, HIP_R, ANK_L, ANK_R)

Landmark = tuple[float, float, float]  # x px, y px, visibility


def _mid(a: Landmark, b: Landmark) -> tuple[float, float]:
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2


def ratios(lm: list[Landmark], t: dict[str, Any] | None = None) -> dict[str, float] | None:
    """None when the photo doesn't show shoulders, hips and ankles clearly."""
    vis = (t or thresholds())["body"]["min_visibility"]
    if len(lm) < 29 or any(lm[i][2] < vis for i in NEEDED):
        return None
    shoulder = math.dist(lm[SH_L][:2], lm[SH_R][:2])
    hip = math.dist(lm[HIP_L][:2], lm[HIP_R][:2])
    torso = math.dist(_mid(lm[SH_L], lm[SH_R]), _mid(lm[HIP_L], lm[HIP_R]))
    leg = math.dist(_mid(lm[HIP_L], lm[HIP_R]), _mid(lm[ANK_L], lm[ANK_R]))
    if min(hip, torso) <= 0:
        return None
    return {"shoulder_hip": shoulder / hip, "leg_torso": leg / torso}


def fit_notes(r: dict[str, float] | None, t: dict[str, Any] | None = None) -> list[dict[str, str]]:
    b = (t or thresholds())["body"]
    notes = [
        {
            "area": "Shirts",
            "advice": "Shoulder seam right on the shoulder point; sleeves ending at the wrist bone.",
        }
    ]
    if r is None:
        notes.append(
            {
                "area": "Photo",
                "advice": "Add a front photo that shows you head to ankles for more fit notes.",
            }
        )
        return notes
    sh = r["shoulder_hip"]
    if sh >= b["broad_shoulders"]:
        notes.append(
            {
                "area": "Jackets",
                "advice": "Soft or natural shoulders sit well; straight or slightly tapered trousers keep the line balanced.",
            }
        )
    elif sh <= b["narrow_shoulders"]:
        notes.append(
            {
                "area": "Jackets",
                "advice": "A little structure at the shoulder gives a clean line; straight-leg trousers pair well.",
            }
        )
    else:
        notes.append(
            {
                "area": "Jackets",
                "advice": "Most cuts work. Choose by how the shoulder seam and the waist sit.",
            }
        )
    lt = r["leg_torso"]
    if lt >= b["long_legs"]:
        notes.append(
            {
                "area": "Trousers",
                "advice": "A slight break at the shoe looks natural; tucked or untucked shirts both work.",
            }
        )
    elif lt <= b["short_legs"]:
        notes.append(
            {
                "area": "Trousers",
                "advice": "A minimal break and a mid rise keep a clean line; shirts work well tucked or cropped at the hip.",
            }
        )
    else:
        notes.append(
            {
                "area": "Trousers",
                "advice": "A slight taper with a minimal break is an easy default.",
            }
        )
    notes.append(
        {
            "area": "Shoes",
            "advice": "Match the shoe to the trouser: sleek profiles with tapered legs, chunkier soles with wider ones.",
        }
    )
    return notes


def height_notes(height_cm: int | None, leg_torso: float | None = None) -> list[dict[str, str]]:
    """Length notes from your height (and leg-to-torso ratio when a full-body photo gave one).
    Common tailoring guidance about lengths and proportions; no judgments about the body."""
    if not height_cm:
        return [
            {
                "area": "Lengths",
                "advice": "Add your height in Settings for notes on jacket and hem lengths.",
            }
        ]
    notes: list[dict[str, str]] = []
    if height_cm < 170:
        notes.append(
            {
                "area": "Lengths",
                "advice": "Tops that end at mid-hip and jackets that just cover the seat keep proportions clean; hem trousers with little or no break.",
            }
        )
        notes.append(
            {
                "area": "Outfits",
                "advice": "Tonal outfits (top and trousers in close shades) give one long line; keep patterns small to medium.",
            }
        )
    elif height_cm > 185:
        notes.append(
            {
                "area": "Lengths",
                "advice": "Longer coats and jackets sit in proportion; a single soft break at the shoe; check that sleeves and tops are long enough.",
            }
        )
        notes.append(
            {
                "area": "Outfits",
                "advice": "Bolder patterns and layered looks carry well; contrast between top and trousers breaks up the line nicely.",
            }
        )
    else:
        notes.append(
            {
                "area": "Lengths",
                "advice": "Standard lengths fit: a slight break at the shoe and jackets that cover the seat.",
            }
        )
    if leg_torso is not None and height_cm:
        if leg_torso < 1.25:
            notes.append(
                {
                    "area": "Rise",
                    "advice": "A mid or high rise and tucked or half-tucked tops lengthen the leg line.",
                }
            )
        elif leg_torso > 1.7:
            notes.append(
                {
                    "area": "Rise",
                    "advice": "Mid-rise trousers and untucked tops that end at the hip keep top and bottom in balance.",
                }
            )
    return notes

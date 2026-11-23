"""`analyze_profile` (SPEC 5.2): skin, contrast, lighting, face shape and body, on this Mac."""

from __future__ import annotations

import io
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
from PIL import Image

from closet_worker.vision import face_shape as fs
from closet_worker.vision import skin
from closet_worker.vision.body import height_notes
from closet_worker.vision.body import ratios as body_ratios
from closet_worker.vision.style import build

from .context import JobContext
from .tag_item import BadJob


def _rgb(ctx: JobContext, path: str) -> np.ndarray[Any, np.dtype[np.uint8]]:
    assert ctx.items is not None
    return np.asarray(
        Image.open(io.BytesIO(ctx.items.download(path))).convert("RGB"), dtype=np.uint8
    )


@dataclass
class FaceRead:
    read: skin.SkinRead
    ratios: dict[str, float]
    light: str | None
    calibrated: bool = False  # a white paper in the photo removed the light's color cast


def face_shape_vote(reads: list[FaceRead]) -> str | None:
    """Majority vote across face photos (near-boundary shapes flip); ties go to the straightest."""
    votes = [(fs.classify(x.ratios), x.ratios["yaw"]) for x in reads]
    shapes = [v for v, _ in votes if v is not None]
    if not shapes:
        return None
    counts = Counter(shapes)
    top = max(counts.values())
    tied = {v for v, n in counts.items() if n == top}
    return min((y, v) for v, y in votes if v in tied)[1]


def measure(
    faces: list[np.ndarray[Any, Any]], front_rgb: np.ndarray[Any, Any] | None
) -> dict[str, Any]:
    """Combine every face photo that's well lit (all of them if none is); vote on face shape."""
    from closet_worker.vision.landmarks import face_points, pose_points
    from closet_worker.vision.paper import apply_gains, face_box, find_paper

    reads: list[FaceRead] = []
    for rgb in faces:
        pts = face_points(rgb)
        if pts is None:
            continue
        found = find_paper(rgb, face_box(pts)).paper
        fixed = apply_gains(rgb, found.gains) if found else rgb
        read = skin.read_skin(fixed, pts)
        light = skin.lighting_note(fixed, read.face_pixels, calibrated=found is not None)
        reads.append(FaceRead(read, fs.ratios(pts), light, found is not None))
    if not reads:
        raise BadJob("No face found in your close-up. Use a clear, front-facing photo in daylight.")
    good = [x for x in reads if x.light is None] or reads
    med = np.median([x.read.lab for x in good], axis=0)
    lab = (float(med[0]), float(med[1]), float(med[2]))
    hair = [x.read.hair_L for x in good if x.read.hair_L is not None]
    hues = [skin.hue_deg(x.read.lab) for x in good]
    straight = min(reads, key=lambda x: x.ratios["yaw"])
    pose = pose_points(front_rgb) if front_rgb is not None else None
    return {
        "skin_lab": [round(x, 2) for x in lab],
        "hair_L": round(float(np.median(hair)), 2) if hair else None,
        "hue": round(skin.hue_deg(lab), 2),
        "ita": round(skin.ita_deg(lab), 2),
        "photos_used": len(good),
        "photos_calibrated": sum(1 for x in good if x.calibrated),
        # How far apart your photos read (undertone hue, degrees): a big gap = the light changed.
        "hue_spread": round(max(hues) - min(hues), 1) if len(hues) > 1 else 0.0,
        # Set only when every face photo had a lighting problem; otherwise those were just skipped.
        "lighting_note": good[0].light,
        "face_ratios": {k: round(v, 3) for k, v in straight.ratios.items()},
        "face_shape": face_shape_vote(reads),
        "face_shape_votes": [fs.classify(x.ratios) for x in reads],
        "body_ratios": None if pose is None else body_ratios(pose),
    }


def run(payload: dict[str, Any], ctx: JobContext | None) -> dict[str, Any]:
    if ctx is None or ctx.items is None:
        raise BadJob("no item store")
    profile = ctx.items.get_profile()
    overrides = {
        "undertone": profile.get("undertone_override"),
        "contrast": profile.get("contrast_override"),
        "depth": profile.get("depth_override"),
    }
    if payload.get("recompute"):
        prev = profile.get("analysis") or {}
        if not prev.get("measurements"):
            raise BadJob("Analyze your photos first.")
        analysis = build(prev["measurements"], overrides)
    else:
        photos = ctx.items.list_style_photos()
        faces = [p for p in photos if p.get("kind") == "face"]
        front = next((p for p in photos if p.get("kind") == "front"), None)
        if not faces or not front:
            raise BadJob("Add a face close-up and a front photo first.")
        m = measure(
            [_rgb(ctx, str(p["photo_path"])) for p in faces], _rgb(ctx, str(front["photo_path"]))
        )
        analysis = build(m, overrides)
    ratios = (analysis.get("measurements") or {}).get("body_ratios") or {}
    analysis["fit_notes"] = [
        *analysis.get("fit_notes", []),
        *height_notes(profile.get("height_cm"), ratios.get("leg_torso")),
    ]
    ctx.items.update_profile({"analysis": analysis, "analyzed_at": datetime.now(UTC).isoformat()})
    return {"effective": analysis["effective"], "face_shape": analysis["face"].get("shape")}

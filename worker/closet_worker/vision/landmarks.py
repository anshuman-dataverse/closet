"""MediaPipe Face and Pose Landmarkers, downloaded once from Google's public model bucket."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from numpy.typing import NDArray

CACHE = Path("~/.cache/closet").expanduser()
MODELS = {
    "face": (
        "face_landmarker.task",
        "face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    ),
    "pose": (
        "pose_landmarker_full.task",
        "pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task",
    ),
}
BUCKET = "https://storage.googleapis.com/mediapipe-models/"


def model_path(kind: str) -> Path:
    name, rel = MODELS[kind]
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        r = httpx.get(BUCKET + rel, timeout=60, follow_redirects=True)
        r.raise_for_status()
        tmp = path.with_suffix(".part")
        tmp.write_bytes(r.content)
        tmp.rename(path)
    return path


@cache
def _face() -> Any:
    from mediapipe.tasks.python import BaseOptions, vision

    opts = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path("face"))), num_faces=1
    )
    return vision.FaceLandmarker.create_from_options(opts)


@cache
def _pose() -> Any:
    from mediapipe.tasks.python import BaseOptions, vision

    opts = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path("pose")))
    )
    return vision.PoseLandmarker.create_from_options(opts)


def _image(rgb: NDArray[np.uint8]) -> Any:
    import mediapipe as mp

    return mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))


def face_points(rgb: NDArray[np.uint8]) -> list[tuple[float, float]] | None:
    """478 Face Mesh points in pixels, or None when no face is found."""
    r = _face().detect(_image(rgb))
    if not r.face_landmarks:
        return None
    h, w = rgb.shape[:2]
    return [(p.x * w, p.y * h) for p in r.face_landmarks[0]]


def pose_points(rgb: NDArray[np.uint8]) -> list[tuple[float, float, float]] | None:
    """33 Pose points as (x px, y px, visibility), or None when no person is found."""
    r = _pose().detect(_image(rgb))
    if not r.pose_landmarks:
        return None
    h, w = rgb.shape[:2]
    return [(p.x * w, p.y * h, float(p.visibility or 0.0)) for p in r.pose_landmarks[0]]

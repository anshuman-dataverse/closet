"""Export the worker's style tables and golden values for the web palette checker.

Run from the repo root:  (cd worker && uv run python ../scripts/export-style-data.py)
Writes web/lib/style/data.json (tables), web/lib/style/golden.json (expected outputs from the
Python code) web/lib/domain/fits.json (fit choices from vocab/fits.yaml) and
web/lib/domain/looks.json (Shop a look piece types from vocab/looks.yaml).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import yaml  # noqa: E402

from closet_worker.vision import body, face_shape, skin  # noqa: E402
from closet_worker.vision.color import srgb_to_lab  # noqa: E402
from closet_worker.vision.style import build  # noqa: E402

VOCAB = ROOT / "worker" / "closet_worker" / "vocab"
OUT = ROOT / "web" / "lib" / "style"


def load(name: str) -> object:
    return yaml.safe_load((VOCAB / name).read_text())


def tables() -> dict[str, object]:
    return {
        "thresholds": load("style.yaml"),
        "palettes": load("palettes.yaml"),
        "faceTips": load("face_tips.yaml"),
        "colors": {k: str(v).lower() for k, v in load("colors.yaml").items()},  # type: ignore[union-attr]
    }


def golden() -> dict[str, object]:
    rgbs = [[255, 255, 255], [0, 0, 0], [255, 0, 0], [214, 170, 140], [120, 80, 60], [31, 42, 72]]
    labs = [[62, 12, 22], [62, 15, 11], [50, 7, 16], [75, 13, 16], [45, 10, 15], [59.77, 12.77, 10.28]]
    ratios = [
        {"length": 1.50, "jaw": 0.80, "forehead": 0.90, "yaw": 0.0},
        {"length": 1.10, "jaw": 0.85, "forehead": 0.85, "yaw": 0.0},
        {"length": 1.25, "jaw": 0.92, "forehead": 0.90, "yaw": 0.0},
        {"length": 1.30, "jaw": 0.72, "forehead": 0.95, "yaw": 0.0},
        {"length": 1.30, "jaw": 0.72, "forehead": 0.78, "yaw": 0.0},
        {"length": 1.30, "jaw": 0.83, "forehead": 0.86, "yaw": 0.0},
        {"length": 1.30, "jaw": 0.83, "forehead": 0.86, "yaw": 0.2},
    ]
    body_r = [None, {"shoulder_hip": 2.2, "leg_torso": 1.1}, {"shoulder_hip": 1.2, "leg_torso": 1.9},
              {"shoulder_hip": 1.7, "leg_torso": 1.45}]
    m = {"skin_lab": [59.77, 12.77, 10.28], "hair_L": 33.11, "hue": 38.83, "ita": 43.57,
         "face_shape": "round", "face_shape_votes": ["round", "round", "oval"], "body_ratios": None,
         "lighting_note": None}
    builds = []
    for over in ({}, {"undertone": "neutral"}, {"undertone": "warm", "contrast": "high"}):
        a = build(m, over)
        builds.append({"overrides": over, "out": {k: a[k] for k in (
            "computed", "effective", "summary", "best", "neutrals", "careful", "fit_notes",
            "occasion_tips", "face", "borderline")}})
    return {
        "lab": [{"rgb": c, "lab": [round(float(x), 4) for x in srgb_to_lab([c])[0]]} for c in rgbs],
        "tones": [{"lab": lab, "undertone": skin.undertone(tuple(lab)), "depth": skin.depth(tuple(lab)),
                   "hue": round(skin.hue_deg(tuple(lab)), 4), "ita": round(skin.ita_deg(tuple(lab)), 4)} for lab in labs],
        "contrast": [{"skin": s, "hair": h, "out": skin.contrast(s, h)} for s, h in ((60, 40), (60, 25), (70, 15), (60, None))],
        "faceShape": [{"ratios": r, "shape": face_shape.classify(r)} for r in ratios],
        "fitNotes": [{"ratios": r, "notes": body.fit_notes(r)} for r in body_r],
        "build": {"measurements": m, "cases": builds},
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "data.json").write_text(json.dumps(tables(), indent=1, ensure_ascii=False) + "\n")
    (OUT / "golden.json").write_text(json.dumps(golden(), indent=1, ensure_ascii=False) + "\n")
    fits = load("fits.yaml")
    (ROOT / "web" / "lib" / "domain" / "fits.json").write_text(
        json.dumps(fits, indent=1, ensure_ascii=False) + "\n"
    )
    (ROOT / "web" / "lib" / "domain" / "looks.json").write_text(
        json.dumps(load("looks.yaml"), indent=1, ensure_ascii=False) + "\n"
    )
    print("wrote", OUT / "data.json", "golden.json, web/lib/domain/fits.json and looks.json")


if __name__ == "__main__":
    main()

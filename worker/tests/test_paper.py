"""White-paper reference and spot sampling (vision/paper.py, vision/skin.py), offline."""

from __future__ import annotations

import numpy as np

from closet_worker.vision import skin
from closet_worker.vision.paper import apply_gains, find_paper
from closet_worker.vision.style import build

FACE = (300.0, 200.0, 500.0, 460.0)


def scene(
    paper: tuple[int, int, int] | None, bg: tuple[int, int, int] = (60, 90, 70)
) -> np.ndarray:
    img = np.zeros((640, 800, 3), dtype=np.uint8)
    img[:] = bg
    img[200:460, 300:500] = (150, 105, 85)  # the face
    if paper:
        img[220:440, 80:260] = paper  # a sheet held beside it
    return img


def test_finds_a_warm_sheet_and_neutralizes_it() -> None:
    r = find_paper(scene((235, 215, 185)), FACE)
    assert r.paper is not None and r.problem is None
    assert r.paper.cast > 5  # the paper was warm before correction
    fixed = apply_gains(np.array([[[235, 215, 185]]], dtype=np.uint8), r.paper.gains)[0, 0]
    assert abs(int(fixed[0]) - int(fixed[2])) <= 2  # neutral after


def test_no_paper_and_blown_paper_say_what_to_do() -> None:
    assert find_paper(scene(None), FACE).problem == (
        "No white paper found. Hold a plain white sheet beside your face, or tap it."
    )
    assert find_paper(scene((255, 255, 255)), FACE).problem == (
        "The paper is too bright to read. Tilt it a little away from the light."
    )


def test_a_bright_sky_across_the_top_isnt_paper() -> None:
    img = scene(None)
    img[:120] = (230, 232, 235)
    assert find_paper(img, FACE).paper is None


def fake_points() -> list[tuple[float, float]]:
    """478 points spread over the face box, with each sampled spot placed on purpose."""
    pts = [(400.0, 330.0)] * 478
    pts[skin.TOP], pts[skin.CHIN] = (400.0, 200.0), (400.0, 460.0)
    pts[skin.LEFT], pts[skin.RIGHT] = (300.0, 330.0), (500.0, 330.0)
    spots = [(340.0, 330.0), (460.0, 330.0), (350.0, 300.0), (450.0, 300.0), (330.0, 310.0),
             (470.0, 310.0), (345.0, 370.0), (455.0, 370.0), (400.0, 230.0)]  # fmt: skip
    for i, xy in zip(skin.SPOTS.values(), spots, strict=True):
        pts[i] = xy
    return pts


def test_a_spot_on_a_cap_or_paper_is_dropped() -> None:
    img = scene(None)
    pts = fake_points()
    clean = skin.read_skin(img, pts)
    assert clean.dropped == ()
    # The forehead spot lands on a burgundy cap; one cheek is covered by white paper.
    fx, fy = map(int, pts[skin.SPOTS["forehead"]])
    img[fy - 12 : fy + 12, fx - 12 : fx + 12] = (110, 30, 50)
    cx, cy = map(int, pts[skin.SPOTS["cheek_l"]])
    img[cy - 12 : cy + 12, cx - 12 : cx + 12] = (245, 245, 243)
    read = skin.read_skin(img, pts)
    assert set(read.dropped) == {"forehead", "cheek_l"}
    assert np.allclose(read.lab, clean.lab, atol=0.5)  # the read didn't move


def test_depth_override_and_disagreeing_photos() -> None:
    m = {"skin_lab": [59.77, 12.77, 10.28], "hair_L": 33.11, "hue": 38.83, "ita": 43.57,
         "face_shape": "round", "face_shape_votes": ["round"], "body_ratios": None,
         "lighting_note": None, "hue_spread": 20.0}  # fmt: skip
    a = build(m, {"depth": "deep"})
    assert a["computed"]["depth"] == "light" and a["effective"]["depth"] == "deep"
    assert any("disagree by 20°" in n for n in a["borderline"])
    assert not any("disagree" in n for n in build(m, {"undertone": "neutral"})["borderline"])

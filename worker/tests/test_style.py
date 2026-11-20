from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

import numpy as np
import pytest

from closet_worker.jobs import analyze_profile, find_gaps
from closet_worker.jobs.context import JobContext
from closet_worker.recsys.engine import accessory_for, ideas
from closet_worker.recsys.model import Context, History
from closet_worker.recsys.scoring import palette_fit
from closet_worker.text.templates import render
from closet_worker.vision import body, face_shape, skin
from closet_worker.vision.style import build, face_tips, palettes

from .recsys_fixtures import closet, ctx, piece

FIX = {
    "skin_lab": [62.0, 12.0, 17.0],
    "hair_L": 24.0,
    "hue": 54.78,
    "ita": 35.22,
    "face_ratios": {},
    "face_shape": "oval",
    "face_shape_votes": ["oval"],
    "body_ratios": {"shoulder_hip": 1.7, "leg_torso": 1.45},
    "lighting_note": None,
}

# ------------------------------------------------- skin, undertone, contrast, lighting


def fake_points(w: int = 400, h: int = 500) -> list[tuple[float, float]]:
    pts = [(w / 2, h / 2)] * 478
    pts = list(pts)
    pts[skin.LEFT], pts[skin.RIGHT] = (100.0, 260.0), (300.0, 260.0)
    pts[skin.TOP], pts[skin.CHIN] = (200.0, 150.0), (200.0, 420.0)
    pts[skin.CHEEK_L], pts[skin.CHEEK_R], pts[skin.FOREHEAD] = (
        (150.0, 300.0),
        (250.0, 300.0),
        (200.0, 190.0),
    )
    return pts


def face_image(
    skin_rgb: tuple[int, int, int],
    hair_rgb: tuple[int, int, int],
    bg: tuple[int, int, int] = (200, 200, 200),
):  # type: ignore[no-untyped-def]
    a = np.full((500, 400, 3), bg, np.uint8)
    a[150:430, 100:300] = skin_rgb
    a[60:150, 110:290] = hair_rgb
    return a


def test_read_skin_samples_cheeks_and_forehead_and_hair() -> None:
    img = face_image((214, 170, 140), (40, 30, 25))
    r = skin.read_skin(img, fake_points())
    expected = skin.srgb_to_lab(np.array([[214, 170, 140]]))[0]
    assert r.lab == pytest.approx(tuple(expected), abs=0.5)
    assert r.hair_L is not None and r.hair_L < 20


@pytest.mark.parametrize(
    ("lab", "tone"),
    [
        ((60, 12, 22), "warm"),
        ((60, 15, 12), "cool"),
        ((60, 13, 16), "neutral"),
        ((60, 7, 16), "olive"),
    ],
)
def test_undertone_bands(lab: tuple[float, float, float], tone: str) -> None:
    assert skin.undertone(lab) == tone


def test_depth_and_contrast_bands() -> None:
    assert skin.depth((70, 10, 15)) == "light"
    assert skin.depth((45, 10, 15)) == "deep"
    assert skin.contrast(60, 40) == "low"
    assert skin.contrast(60, 25) == "medium"
    assert skin.contrast(70, 15) == "high"
    assert skin.contrast(60, None) is None


def test_lighting_check() -> None:
    def note(img: np.ndarray) -> str | None:  # type: ignore[type-arg]
        return skin.lighting_note(img, skin.read_skin(img, fake_points()).face_pixels)

    assert note(face_image((214, 170, 140), (40, 30, 25))) is None
    assert "dark" in (note(face_image((60, 45, 35), (20, 15, 10), bg=(50, 50, 50))) or "")
    assert (
        "warm" in (note(face_image((230, 180, 120), (60, 40, 20), bg=(240, 190, 90))) or "").lower()
    )
    assert "overexposed" in (note(face_image((255, 255, 255), (40, 30, 25))) or "")


# --------------------------------------------------------------- face shape


@pytest.mark.parametrize(
    ("r", "shape"),
    [
        ({"length": 1.50, "jaw": 0.80, "forehead": 0.90, "yaw": 0.0}, "oblong"),
        ({"length": 1.10, "jaw": 0.85, "forehead": 0.85, "yaw": 0.0}, "round"),
        ({"length": 1.25, "jaw": 0.92, "forehead": 0.90, "yaw": 0.0}, "square"),
        ({"length": 1.30, "jaw": 0.72, "forehead": 0.95, "yaw": 0.0}, "heart"),
        ({"length": 1.30, "jaw": 0.72, "forehead": 0.78, "yaw": 0.0}, "diamond"),
        ({"length": 1.30, "jaw": 0.83, "forehead": 0.86, "yaw": 0.0}, "oval"),
    ],
)
def test_face_shapes(r: dict[str, float], shape: str) -> None:
    assert face_shape.classify(r) == shape


def test_turned_face_gets_no_guess() -> None:
    assert face_shape.classify({"length": 1.3, "jaw": 0.83, "forehead": 0.86, "yaw": 0.2}) is None
    pts = fake_points()
    pts[face_shape.NOSE] = (200.0, 300.0)
    assert face_shape.ratios(pts)["yaw"] == pytest.approx(0.0)
    assert face_shape.ratios(pts)["length"] == pytest.approx(270 / 200)


def test_every_shape_has_tips() -> None:
    for shape in ("oval", "round", "square", "oblong", "heart", "diamond"):
        t = face_tips()[shape]
        assert t["why"] and 2 <= len(t["frames"]) <= 3 and 2 <= len(t["hair"]) <= 3


# --------------------------------------------------------------- body


def pose(
    sh: float, hip: float, torso: float, leg: float, vis: float = 0.9
) -> list[tuple[float, float, float]]:
    lm = [(0.0, 0.0, vis)] * 33
    lm = list(lm)
    lm[11], lm[12] = (200 - sh / 2, 100, vis), (200 + sh / 2, 100, vis)
    lm[23], lm[24] = (200 - hip / 2, 100 + torso, vis), (200 + hip / 2, 100 + torso, vis)
    lm[27], lm[28] = (
        (200 - hip / 2, 100 + torso + leg, vis),
        (200 + hip / 2, 100 + torso + leg, vis),
    )
    return lm


def test_body_ratios_and_notes() -> None:
    r = body.ratios(pose(180, 100, 150, 225))
    assert r == pytest.approx({"shoulder_hip": 1.8, "leg_torso": 1.5})
    assert body.ratios(pose(180, 100, 150, 225, vis=0.2)) is None
    areas = [n["area"] for n in body.fit_notes(r)]
    assert areas == ["Shirts", "Jackets", "Trousers", "Shoes"]
    assert body.fit_notes(None)[-1]["area"] == "Photo"


# --------------------------------------------------------------- palettes, text, overrides


def test_every_palette_combination_exists_and_is_well_formed() -> None:
    p = palettes()
    from closet_worker.vision.style import color_hex

    for u in ("warm", "cool", "neutral", "olive"):
        for d in ("light", "medium", "deep"):
            for c in ("low", "medium", "high"):
                e = p[f"{u}/{d}/{c}"]
                assert (
                    6 <= len(e["best"]) <= 8
                    and 3 <= len(e["neutrals"]) <= 5
                    and 2 <= len(e["careful"]) <= 4
                )
                names = e["best"] + e["neutrals"] + [x["name"] for x in e["careful"]]
                assert all(n in color_hex() for n in names)
                assert all(x["why"].endswith(".") for x in e["careful"])
                assert not set(e["best"]) & {x["name"] for x in e["careful"]}


BANNED = re.compile(
    r"\b(weight|fat|thin|skinny|slim|slimming|slimmer|overweight|chubby|diet|lose|hide|attractive|unattractive|"
    r"ugly|pretty|handsome|beautiful|flatter|flattering)\b",
    re.I,
)


def _strings(x: Any) -> list[str]:
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [
            s for k, v in x.items() if k not in ("measurements", "thresholds") for s in _strings(v)
        ]
    if isinstance(x, list):
        return [s for v in x for s in _strings(v)]
    return []


@pytest.mark.parametrize("shape", ["oval", "round", "square", "oblong", "heart", "diamond", None])
@pytest.mark.parametrize(
    "bodyr",
    [None, {"shoulder_hip": 2.2, "leg_torso": 1.1}, {"shoulder_hip": 1.2, "leg_torso": 1.9}],
)
def test_no_body_or_looks_judgments_anywhere(
    shape: str | None, bodyr: dict[str, float] | None
) -> None:
    for lab in ([62, 12, 22], [62, 15, 11], [50, 7, 16], [75, 13, 16]):
        a = build({**FIX, "skin_lab": lab, "face_shape": shape, "body_ratios": bodyr})
        for s in _strings(a):
            assert not BANNED.search(s), s


def test_overrides_win() -> None:
    a = build(FIX)
    b = build(FIX, {"undertone": "cool", "contrast": "high"})
    assert a["effective"]["undertone"] != "cool"
    assert b["effective"] == {
        "undertone": "cool",
        "depth": a["effective"]["depth"],
        "contrast": "high",
    }
    assert b["computed"] == a["computed"]
    assert [c["name"] for c in b["best"]] != [c["name"] for c in a["best"]]
    assert "Change" not in " ".join(b["borderline"])  # overridden reads don't nag


class ProfileStore:
    owner = "o"

    def __init__(self, analysis: dict[str, Any] | None, **over: Any) -> None:
        self.p: dict[str, Any] = {"analysis": analysis, **over}

    def get_profile(self) -> dict[str, Any]:
        return self.p

    def update_profile(self, f: dict[str, Any]) -> None:
        self.p.update(f)

    def list_style_photos(self) -> list[dict[str, Any]]:
        return []


def test_recompute_uses_stored_measurements_and_overrides(settings) -> None:  # type: ignore[no-untyped-def]
    st = ProfileStore(build(FIX), undertone_override="olive")
    out = analyze_profile.run({"recompute": True}, JobContext(settings=settings, items=st))  # type: ignore[arg-type]
    assert (
        out["effective"]["undertone"] == "olive"
        and st.p["analysis"]["effective"]["undertone"] == "olive"
    )


def test_full_run_needs_face_and_front(settings) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(Exception, match="face close-up and a front photo"):
        analyze_profile.run({}, JobContext(settings=settings, items=ProfileStore(None)))  # type: ignore[arg-type]


# --------------------------------------------------------------- recommender integration


def test_palette_fit_prefers_best_colors_and_penalizes_careful_near_face() -> None:
    a = build(
        FIX, {"undertone": "cool", "contrast": "medium"}
    )  # best: navy, burgundy…; careful: orange…
    navy = (piece("t", "Tops", color_name="navy"), piece("b", "Bottoms", color_name="grey"))
    orange = (piece("t", "Tops", color_name="orange"), piece("b", "Bottoms", color_name="grey"))
    v1, r1 = palette_fit(navy, a)
    v2, _ = palette_fit(orange, a)
    assert v1 > v2
    assert r1 and r1[0]["kind"] == "palette" and r1[0]["color"] == "navy"
    assert palette_fit(navy, None) == (0.0, [])
    assert "navy is one of your best colors" in render(
        r1, seed=0
    ).lower() or "best colors" in render(r1, seed=1)


def test_accessories_follow_the_rules() -> None:
    pcs = [
        *closet(),
        piece("watch", "Accessories", type="watch"),
        piece("belt", "Accessories", type="belt"),
        piece("shades", "Accessories", type="sunglasses"),
        piece("cap", "Accessories", type="cap"),
    ]
    o = (piece("t", "Tops"), piece("b", "Bottoms", type="chinos"))
    sunny_college = Context(occasion="college", day=date(2026, 11, 20), code=1)
    got = accessory_for(o, pcs, sunny_college, History())
    assert got is not None and got.type in {"belt", "sunglasses", "cap"}
    assert accessory_for(o, pcs, ctx(), History()).type in {"watch", "belt"}  # type: ignore[union-attr]
    jog = (piece("t", "Tops"), piece("j", "Bottoms", type="joggers"))
    office_cloudy = Context(occasion="office", day=date(2026, 11, 20), code=3)
    assert (
        accessory_for(jog, [p for p in pcs if p.type != "watch"], office_cloudy, History()) is None
    )


def test_ideas_add_at_most_one_accessory_and_keep_structure() -> None:
    pcs = [*closet(), piece("watch", "Accessories", type="watch")]
    for o, s in ideas(pcs, ctx(temp_high_f=70.0), History()):
        cats = [p.category for p in o]
        assert cats.count("Accessories") <= 1
        assert cats.count("Tops") == 1 and cats.count("Bottoms") == 1
        if "Accessories" in cats:
            assert any(r["kind"] == "accessory" for r in s.reasons)


def test_find_gaps_uses_your_palette(settings) -> None:  # type: ignore[no-untyped-def]
    a = build(FIX, {"undertone": "cool", "contrast": "medium"})
    best = {c["name"].lower() for c in a["best"]}
    neutrals = {c["name"].lower() for c in a["neutrals"]}
    ideas_ = find_gaps.gap_ideas([p for p in closet()], ctx(), History(), a)
    assert ideas_
    for i in ideas_:
        allowed = best if i["category"] in ("Tops", "Layers", "Sets & suits") else neutrals
        assert i["color_name"] in allowed
    assert math.isfinite(sum(i["unlocks"] for i in ideas_))

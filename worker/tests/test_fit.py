"""Fit from a photo (vision/fit.py): choices, outline rules, combination, the gate, tag_item."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from closet_worker.vision import fit as F

from .stubs import StubEmbedder


def pants(thigh: float, knee: float, hem: float, h: int = 400, length_scale: float = 1.0) -> Any:
    """A flat-lay pants mask: waistband, then two legs whose width goes thigh → knee → hem."""
    h = int(h * length_scale)
    w = 400
    m = np.zeros((h + 40, w), dtype=bool)
    for y in range(h):
        f = y / h
        if f < 0.15:
            leg = thigh
            m[20 + y, int(w / 2 - leg) : int(w / 2 + leg)] = True
            continue
        if f < 0.6:
            leg = thigh + (knee - thigh) * (f - 0.15) / 0.45
        else:
            leg = knee + (hem - knee) * (f - 0.6) / 0.4
        gap = 6
        m[20 + y, int(w / 2 - gap - leg) : int(w / 2 - gap)] = True
        m[20 + y, int(w / 2 + gap) : int(w / 2 + gap + leg)] = True
    return m


def top(body_w: int, length: int) -> Any:
    m = np.zeros((length + 40, body_w + 200), dtype=bool)
    m[20 : 20 + length, 100 : 100 + body_w] = True
    m[20:80, 30:100] = True  # a sleeve
    m[20:80, 100 + body_w : 170 + body_w] = True
    return m


@pytest.mark.parametrize(
    ("mask", "shape"),
    [
        (pants(60, 45, 70), "flare"),
        (pants(60, 45, 28), "taper"),
        (pants(60, 52, 52), "straight"),
        (pants(140, 125, 125), "wide"),
    ],
)
def test_pants_shapes(mask: Any, shape: str) -> None:
    assert F.shape_of(F.measure(mask, "bottoms"), "bottoms") == shape


@pytest.mark.parametrize(
    ("w", "length", "shape"),
    [(240, 400, "narrow"), (290, 400, "regular"), (360, 400, "wide"), (460, 400, "short")],
)
def test_top_shapes_ignore_sleeves(w: int, length: int, shape: str) -> None:
    assert F.shape_of(F.measure(top(w, length), "tops"), "tops") == shape


def test_unusable_outlines() -> None:
    assert F.measure(np.ones((300, 300), dtype=bool), "bottoms") is None  # no cut-out
    assert F.measure(np.zeros((300, 300), dtype=bool), "tops") is None
    assert F.shape_of(None, "bottoms") is None


def test_options_follow_category_and_wears() -> None:
    ids = lambda c, w: [f.id for f in F.options(c, w)]  # noqa: E731
    assert "flare" in ids("Bottoms", "menswear") and "barrel" not in ids("Bottoms", "menswear")
    assert "barrel" in ids("Bottoms", "womenswear")
    assert "cropped" in ids("Tops", None) and "cropped" not in ids("Layers", "menswear")
    assert ids("Shoes", "menswear") == [] and ids("Accessories", None) == []
    assert F.options("Sets & suits", "both") == F.options("Sets & suits", None)


def fits(*specs: tuple[str, str | None]) -> list[F.Fit]:
    return [F.Fit(i, i, ("menswear",), i, s) for i, s in specs]


def test_combine_needs_agreement_or_a_silent_shape() -> None:
    fs = fits(("skinny", "taper"), ("flare", "flare"), ("relaxed", None))
    p = np.array([0.2, 0.7, 0.1])
    assert F.combine(fs, p, "flare") == ("flare", "both")
    assert F.combine(fs, p, "taper") == (None, "none")  # they disagree: no guess
    assert F.combine(fs, p, None) == ("flare", "photo")  # no outline, photo model sure enough
    assert F.combine(fs, np.array([0.4, 0.35, 0.25]), None) == (None, "none")  # not sure enough
    assert F.combine(fs, np.array([0.1, 0.1, 0.8]), "taper") == ("relaxed", "photo")


def test_guess_fit_skips_shoes_and_reports_reads() -> None:
    emb = StubEmbedder(target="a photo of flared jeans")
    vec = emb.image([None])[0]  # type: ignore[list-item]
    assert F.guess_fit(vec, None, "Shoes", "sneakers", "menswear", emb) is None
    g = F.guess_fit(vec, pants(60, 45, 70), "Bottoms", "jeans", "menswear", emb)
    assert g is not None and g.shape == "flare" and g.photo_fit == "flare"
    assert g.fit == "flare" and g.method == "both"
    assert {r["fit"] for r in g.ranked} == {f.id for f in F.options("Bottoms", "menswear")}


def write_gate(path: Path, per_fit: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"per_fit": per_fit}))
    return path


def test_gate_rechecks_the_numbers(tmp_path: Path) -> None:
    assert F.read_gate(tmp_path / "none.json") == frozenset()
    g = write_gate(
        tmp_path / "gate.json",
        {
            "bottoms/flare": {"suggested": 8, "precision": 0.875},
            "bottoms/slim": {"suggested": 3, "precision": 1.0},  # too few to trust
            "tops/oversized": {"suggested": 10, "precision": 0.6},  # not right often enough
        },
    )
    assert F.read_gate(g) == frozenset({"bottoms/flare"})
    assert F.gate_key("Layers", "slim") == "tops/slim" and F.gate_key("Shoes", "x") is None

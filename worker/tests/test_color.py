from __future__ import annotations

import numpy as np
import pytest

from closet_worker.vision.color import (
    Palette,
    delta_e,
    dominant_colors,
    primary_secondary,
    srgb_to_lab,
)
from closet_worker.vocab import load_vocab

from .stubs import two_color_image

PALETTE = Palette.from_dict(load_vocab().colors)


def test_lab_reference_values() -> None:
    lab = srgb_to_lab(np.array([[255, 255, 255], [0, 0, 0], [255, 0, 0]]))
    assert lab[0] == pytest.approx([100, 0, 0], abs=0.01)
    assert lab[1] == pytest.approx([0, 0, 0], abs=0.01)
    assert lab[2] == pytest.approx([53.24, 80.09, 67.20], abs=0.05)


@pytest.mark.parametrize(
    ("lab1", "lab2", "expected"),
    [  # Sharma, Wu & Dalal (2005) test data
        ((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425),
        ((50, 0, 0), (50, -1, 2), 2.3669),
        ((50, 2.5, 0), (73, 25, -18), 27.1492),
        ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ],
)
def test_delta_e_2000(lab1: tuple[float, ...], lab2: tuple[float, ...], expected: float) -> None:
    assert float(delta_e(np.array([lab1]), np.array([lab2]))[0]) == pytest.approx(
        expected, abs=1e-3
    )


@pytest.mark.parametrize(
    ("rgb", "name"),
    [
        ((31, 42, 72), "navy"),
        ((246, 246, 243), "white"),
        ((138, 143, 152), "grey"),
        ((178, 38, 30), "red"),
    ],
)
def test_naming(rgb: tuple[int, int, int], name: str) -> None:
    assert PALETTE.nearest(srgb_to_lab(np.array([rgb]))[0])[0] == name


def test_primary_and_secondary_over_20_percent() -> None:
    img = np.asarray(two_color_image((31, 42, 72), (246, 246, 243), 0.35))
    mask = img.mean(axis=2) < 250  # the block, not the white canvas around it
    mask[10:38, 10:90] = True  # the white band is part of the piece
    p, s = primary_secondary(dominant_colors(img, mask, PALETTE))
    assert p.name == "navy"
    assert s is not None and s.name in {"white", "off-white"}
    assert 0.3 < s.share < 0.4


def test_small_second_color_is_dropped() -> None:
    img = np.asarray(two_color_image((31, 42, 72), (178, 38, 30), 0.1))
    mask = np.zeros(img.shape[:2], bool)
    mask[10:90, 10:90] = True
    p, s = primary_secondary(dominant_colors(img, mask, PALETTE))
    assert p.name == "navy" and s is None


def test_single_color_image_does_not_crash() -> None:
    img = np.full((20, 20, 3), (31, 42, 72), np.uint8)
    out = dominant_colors(img, None, PALETTE)
    assert out[0].name == "navy" and out[0].share == pytest.approx(1.0)

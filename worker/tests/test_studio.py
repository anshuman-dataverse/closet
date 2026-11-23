"""Studio images (vision/studio.py): framing, background, and true color."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from closet_worker.vision.studio import BACKGROUND, main_piece, make_studio


def scene() -> tuple[np.ndarray, np.ndarray]:
    rgb = np.full((800, 600, 3), 200, np.uint8)
    rgb[200:600, 150:450] = (31, 42, 72)  # a navy garment
    mask = np.zeros((800, 600), bool)
    mask[200:600, 150:450] = True
    return rgb, mask


def test_frames_the_piece_on_the_studio_background() -> None:
    rgb, mask = scene()
    st = make_studio(rgb, mask)
    assert st is not None
    img = np.asarray(Image.open(io.BytesIO(st.full)))
    assert img.shape == (1200, 1200, 3)
    for y, x in ((10, 10), (600, 1190)):  # JPEG shifts flat colors by a level or two
        assert np.abs(img[y, x].astype(int) - BACKGROUND).max() <= 2
    center = img[600, 600].astype(int)
    # Exposure may lift brightness a little, but the hue stays navy (blue > red, green).
    assert center[2] > center[0] and center[2] > center[1] and abs(center - [31, 42, 72]).max() < 20


def test_keeps_the_piece_drops_far_fragments() -> None:
    _, mask = scene()
    mask[20:60, 20:60] = True  # a separate scrap of background
    mask[380:420, 450:470] = True  # touching the piece by a thin bridge, then a blob
    mask[300:500, 470:560] = True
    keep = main_piece(mask)
    assert not keep[40, 40] and keep[400, 300]


def test_no_cut_out_means_no_studio() -> None:
    rgb, _ = scene()
    assert make_studio(rgb, np.zeros((800, 600), bool)) is None
    assert make_studio(rgb, np.ones((800, 600), bool)) is None


def test_tops_get_a_hanger_and_shoes_dont() -> None:
    rgb, mask = scene()
    hook_zone = (slice(30, 140), slice(560, 640))  # above the piece, at its center

    def metal_pixels(category: str | None) -> int:
        st = make_studio(rgb, mask, category)
        assert st is not None
        img = np.asarray(Image.open(io.BytesIO(st.full))).astype(int)[hook_zone]
        grey = (abs(img[..., 0] - img[..., 1]) < 8) & (img[..., 0] < 200) & (img[..., 0] > 100)
        return int(grey.sum())

    assert metal_pixels("Tops") > 50
    assert metal_pixels("Shoes") == 0 and metal_pixels(None) == 0

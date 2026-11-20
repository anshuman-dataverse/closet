from __future__ import annotations

import io

import numpy as np
from PIL import Image

from closet_worker.vision.cutout import compose, mask_bbox
from closet_worker.vocab import CATEGORIES, OCCASIONS, WARMTH, load_vocab


def test_bbox_pads_5_percent_and_clips() -> None:
    m = np.zeros((200, 100), bool)
    m[50:150, 20:80] = True  # 100 tall, 60 wide
    assert mask_bbox(m) == (17, 45, 83, 155)
    edge = np.zeros((10, 10), bool)
    edge[0:10, 0:10] = True
    assert mask_bbox(edge) == (0, 0, 10, 10)


def test_compose_makes_transparent_webp_and_white_crop() -> None:
    a = np.full((100, 100, 3), 255, np.uint8)
    a[20:80, 30:70] = (31, 42, 72)
    out = compose(Image.fromarray(a), a.mean(axis=2) < 200)
    webp = Image.open(io.BytesIO(out.webp))
    assert webp.mode == "RGBA" and webp.format == "WEBP"
    assert webp.getpixel((0, 0))[3] == 0  # padding is transparent
    assert out.crop.getpixel((0, 0)) == (255, 255, 255)


def test_empty_mask_falls_back_to_whole_photo() -> None:
    out = compose(Image.new("RGB", (40, 40), (10, 10, 10)), np.zeros((40, 40), bool))
    assert out.mask.all()


def test_vocab_integrity() -> None:
    v = load_vocab()
    assert len(v.types) >= 80
    assert len({t.type for t in v.types}) == len(v.types)
    for t in v.types:
        assert t.category in CATEGORIES, t
        assert 1 <= t.formality <= 5, t
        assert t.warmth in WARMTH, t
        assert t.occasions and set(t.occasions) <= set(OCCASIONS), t
    assert {"kurta", "nehru jacket", "quarter-zip sweater", "varsity jacket", "cargo trousers"} <= {
        t.type for t in v.types
    }
    assert 35 <= len(v.colors) <= 45
    assert set(v.patterns) == {"solid", "striped", "checked", "printed", "textured"}

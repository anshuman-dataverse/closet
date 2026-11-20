"""Deterministic stand-ins for model-backed pieces, so tests never download weights."""

from __future__ import annotations

import hashlib

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from closet_worker.vision.embed import l2


def _vec(text: str, dim: int = 32) -> NDArray[np.float32]:
    seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "little")
    return l2(np.random.default_rng(seed).standard_normal(dim))


class StubEmbedder:
    """Images embed to whatever text `target` would; clothing-ness via `clothing`."""

    model_id = "stub"
    dim = 32
    logit_scale = 100.0

    def __init__(
        self, target: str = "a photo of a oxford shirt", clothing: bool = True, scale: float = 100.0
    ) -> None:
        self.target = target
        self.clothing = clothing
        self.logit_scale = scale  # a flat scale makes every type about equally likely

    def text(self, prompts: list[str]) -> NDArray[np.float32]:
        return np.stack([_vec(p) for p in prompts])

    def image(self, imgs: list[Image.Image]) -> NDArray[np.float32]:
        v = _vec(self.target) + 0.6 * _vec(
            "a photo of clothing" if self.clothing else "a photo of food"
        )
        return np.stack([l2(v) for _ in imgs])


class StubCutter:
    """Mask = every non-white pixel."""

    def cut(self, img: Image.Image):  # type: ignore[no-untyped-def]
        from closet_worker.vision.cutout import compose

        a = np.asarray(img.convert("RGB"))
        return compose(img, a.mean(axis=2) < 235)


def two_color_image(
    c1: tuple[int, int, int], c2: tuple[int, int, int], share2: float, size: int = 100
) -> Image.Image:
    """A white canvas with a garment block: c1 with a share2 band of c2."""
    a = np.full((size, size, 3), 255, np.uint8)
    a[10:90, 10:90] = c1
    rows = int(80 * share2)
    if rows:
        a[10 : 10 + rows, 10:90] = c2
    return Image.fromarray(a)

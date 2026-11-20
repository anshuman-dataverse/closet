"""Background removal with rembg (SPEC 5.1 step 2): mask, transparent WebP cutout, padded crop."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

REMBG_MODEL = "isnet-general-use"
PAD = 0.05
# Below this share the mask is treated as a miss and the whole photo is used.
MIN_MASK_SHARE = 0.01


def mask_bbox(mask: NDArray[np.bool_], pad: float = PAD) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of the mask, padded by `pad` of its size, clipped to the image."""
    h, w = mask.shape
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return 0, 0, w, h
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    px, py = round((x1 - x0) * pad), round((y1 - y0) * pad)
    return max(0, x0 - px), max(0, y0 - py), min(w, x1 + px), min(h, y1 + py)


@dataclass
class Cutout:
    mask: NDArray[np.bool_]
    rgb: NDArray[np.uint8]  # the full photo as an array
    crop: Image.Image  # the piece on white, cropped to the padded mask box (what gets embedded)
    webp: bytes  # transparent cutout, cropped, for flat-lays


def compose(img: Image.Image, mask: NDArray[np.bool_]) -> Cutout:
    rgb_img = img.convert("RGB")
    rgb = np.asarray(rgb_img, dtype=np.uint8)
    if mask.mean() < MIN_MASK_SHARE:
        mask = np.ones(mask.shape, dtype=bool)
    box = mask_bbox(mask)
    alpha = Image.fromarray((mask * 255).astype(np.uint8), "L")
    rgba = rgb_img.copy()
    rgba.putalpha(alpha)
    rgba = rgba.crop(box)
    white = Image.new("RGB", rgba.size, (255, 255, 255))
    white.paste(rgba, mask=rgba.getchannel("A"))
    buf = io.BytesIO()
    rgba.save(buf, "WEBP", quality=85, method=4)
    return Cutout(mask=mask, rgb=rgb, crop=white, webp=buf.getvalue())


class Cutter:
    """Lazy rembg session; the model downloads (~170 MB) on first use and stays in memory."""

    def __init__(self, model: str = REMBG_MODEL) -> None:
        self.model = model
        self._session: Any = None

    def mask(self, img: Image.Image) -> NDArray[np.bool_]:
        from rembg import new_session, remove

        if self._session is None:
            self._session = new_session(self.model)
        m = remove(
            img.convert("RGB"), session=self._session, only_mask=True, post_process_mask=True
        )
        arr = np.asarray(m if isinstance(m, Image.Image) else Image.open(io.BytesIO(bytes(m))))
        return np.asarray(arr > 127, dtype=bool)

    def cut(self, img: Image.Image) -> Cutout:
        return compose(img, self.mask(img))

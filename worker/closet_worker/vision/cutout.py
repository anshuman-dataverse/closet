"""Background removal with rembg (SPEC 5.1 step 2): mask, transparent WebP cutout, padded crop."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

REMBG_MODEL = "isnet-general-use"
# Clothing segmentation (rembg u2net_cloth_seg, trained on iMaterialist garments): separates the
# garment from hands, hangers and the rail. Edges still come from REMBG_MODEL.
GARMENT_MODEL = "u2net_cloth_seg"
GARMENT_MIN_SHARE = 0.02
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

    def __init__(self, model: str = REMBG_MODEL, garment_model: str | None = GARMENT_MODEL) -> None:
        self.model = model
        self.garment_model = garment_model
        self._session: Any = None
        self._garment: Any = None

    def _edges(self, img: Image.Image) -> NDArray[np.bool_]:
        from rembg import new_session, remove

        if self._session is None:
            self._session = new_session(self.model)
        m = remove(
            img.convert("RGB"), session=self._session, only_mask=True, post_process_mask=True
        )
        arr = np.asarray(m if isinstance(m, Image.Image) else Image.open(io.BytesIO(bytes(m))))
        return np.asarray(arr > 127, dtype=bool)

    def _garment_area(self, img: Image.Image) -> NDArray[np.bool_] | None:
        """Where the clothing model sees a garment (upper, lower or full body), or None if it
        sees none (shoes, bags and other accessories aren't in what it was trained on)."""
        if self.garment_model is None:
            return None
        from rembg import new_session

        if self._garment is None:
            self._garment = new_session(self.garment_model)
        masks = self._garment.predict(img.convert("RGB"))
        area = np.zeros((img.height, img.width), dtype=bool)
        for m in masks:
            area |= np.asarray(m.convert("L").resize(img.size)) > 127
        return area if area.mean() >= GARMENT_MIN_SHARE else None

    def mask(self, img: Image.Image) -> NDArray[np.bool_]:
        """The precise model draws the edge; the clothing model decides what's garment, so a
        hand, hanger hook, wall or the next shirt on the rail is left out."""
        edges = self._edges(img)
        area = self._garment_area(img)
        if area is None:
            return edges
        from scipy.ndimage import binary_dilation
        from skimage.morphology import disk

        small = max(1, round(min(area.shape) / 400))
        a = binary_dilation(area[::small, ::small], structure=disk(3))
        grown = np.kron(a, np.ones((small, small), dtype=bool))
        grown = np.pad(
            grown[: area.shape[0], : area.shape[1]],
            (
                (0, max(0, area.shape[0] - grown.shape[0])),
                (0, max(0, area.shape[1] - grown.shape[1])),
            ),
            mode="edge",
        )
        both = edges & grown
        # If the two disagree badly (the clothing model missed most of the piece), trust edges.
        return both if both.sum() >= 0.5 * area.sum() else edges

    def cut(self, img: Image.Image) -> Cutout:
        return compose(img, self.mask(img))

"""Studio image: the cut-out piece, centered on a clean background like a product photo.

Only presentation changes: framing, background, a soft shadow, and a gentle exposure and
sharpness fix. The garment's shape and color are not altered (no generative editing), and the
exposure fix is bounded so the color you see stays true. Tagging and color naming keep using the
original photo.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageFilter

SIZE = 1200
THUMB = 480
BACKGROUND = (244, 243, 240)  # light warm grey, like a studio sweep
FILL = 0.82  # the piece's longer side takes this share of the frame
SHADOW_OPACITY = 0.16
MAX_GAIN = 1.12  # exposure lift is capped: brighter, never a different color
MIN_MASK_SHARE = 0.01


@dataclass
class Studio:
    full: bytes  # SIZE×SIZE JPEG
    thumb: bytes  # THUMB×THUMB JPEG


def _levels(rgb: NDArray[np.float64], mask: NDArray[np.bool_]) -> NDArray[np.float64]:
    """Lift a dim photo: scale so the piece's bright end reaches ~96%, by at most MAX_GAIN.
    One gain for all three channels, so hue and saturation are unchanged."""
    px = rgb[mask]
    if px.size == 0:
        return rgb
    lum = px @ np.array([0.2126, 0.7152, 0.0722])
    hi = float(np.percentile(lum, 99))
    gain = min(MAX_GAIN, 245.0 / hi) if hi > 0 else 1.0
    return np.clip(rgb * max(1.0, gain), 0, 255)


def main_piece(mask: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """Keep the garment, drop leftover background fragments. Thin bridges (a hanger hook, the
    edge of a wall) are cut first, then the largest shape is kept with any other shape at least
    15% its size (a second sleeve), and finally the piece's own fine edges are restored."""
    from scipy.ndimage import binary_dilation, binary_opening
    from skimage.measure import label
    from skimage.morphology import disk

    small = max(1, round(min(mask.shape) / 400))  # work on a smaller copy for speed
    m = mask[::small, ::small]
    r = max(2, round(min(m.shape) * 0.012))
    opened = binary_opening(m, structure=disk(r))
    lab = label(opened, connectivity=2)
    if lab.max() == 0:
        return mask
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    core = np.isin(lab, np.flatnonzero(sizes >= 0.15 * sizes.max()))
    near = binary_dilation(core, structure=disk(r + 1))
    near_full = np.kron(near, np.ones((small, small), dtype=bool))[: mask.shape[0], : mask.shape[1]]
    pad_h, pad_w = mask.shape[0] - near_full.shape[0], mask.shape[1] - near_full.shape[1]
    if pad_h or pad_w:
        near_full = np.pad(near_full, ((0, pad_h), (0, pad_w)), mode="edge")
    return mask & near_full


def make_studio(rgb: NDArray[np.uint8], mask: NDArray[np.bool_]) -> Studio | None:
    """None when there's no usable cut-out (then the app keeps showing the photo)."""
    if mask.mean() < MIN_MASK_SHARE or mask.all():
        return None
    mask = main_piece(mask)
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    crop = rgb[y0:y1, x0:x1].astype(np.float64)
    m = mask[y0:y1, x0:x1]
    crop = _levels(crop, m)
    h, w = m.shape
    scale = (SIZE * FILL) / max(h, w)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    piece = Image.fromarray(crop.astype(np.uint8), "RGB").resize((nw, nh), Image.Resampling.LANCZOS)
    alpha = Image.fromarray((m * 255).astype(np.uint8), "L").resize(
        (nw, nh), Image.Resampling.LANCZOS
    )
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.8))  # soften the cut edge a little
    piece = piece.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=3))

    canvas = Image.new("RGB", (SIZE, SIZE), BACKGROUND)
    left, top = (SIZE - nw) // 2, (SIZE - nh) // 2
    # Soft contact shadow: the silhouette, blurred, nudged down, faint.
    shadow = Image.new("L", (SIZE, SIZE), 0)
    shadow.paste(alpha, (left, top + round(SIZE * 0.015)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(SIZE * 0.02))
    shade = Image.new("RGB", (SIZE, SIZE), (90, 86, 80))
    canvas = Image.composite(shade, canvas, shadow.point(lambda v: int(v * SHADOW_OPACITY)))
    canvas.paste(piece, (left, top), alpha)

    def jpeg(img: Image.Image) -> bytes:
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=88, optimize=True, progressive=True)
        return buf.getvalue()

    return Studio(jpeg(canvas), jpeg(canvas.resize((THUMB, THUMB), Image.Resampling.LANCZOS)))

"""Zero-shot tags from a fashion CLIP model (SPEC 5.1 steps 4–8)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from closet_worker.vocab import TypeEntry, Vocab

from .color import Palette, dominant_colors, primary_secondary
from .embed import Embedder, l2

UNSURE_BELOW = 0.35
TYPE_TEMPLATES = ("a photo of a {}", "a product photo of a {}, on a plain background")
# CLIP models don't understand negation ("not clothing"), so the clothing check compares
# clothing prompts against concrete non-clothing scenes instead (SPEC 5.1 step 8, adapted).
CLOTHING_PROMPTS = (
    "a photo of clothing",
    "a photo of a garment",
    "a photo of a pair of shoes",
    "a photo of a fashion accessory",
)
NOT_CLOTHING_PROMPTS = (
    "a photo of food",
    "a photo of a room interior",
    "a close-up photo of a person's face",
    "a photo of a pet",
    "a photo of a landscape",
    "a screenshot of text",
    "a photo of furniture",
    "a photo of a car",
    "a photo of electronics",
)


def softmax(x: NDArray[np.floating]) -> NDArray[np.float64]:
    z = np.asarray(x, dtype=np.float64)
    z = np.exp(z - z.max(axis=-1, keepdims=True))
    return np.asarray(z / z.sum(axis=-1, keepdims=True), dtype=np.float64)


@dataclass
class Suggestions:
    name: str
    category: str
    type: str
    color_name: str
    color_hex: str
    secondary_color: str | None
    pattern: str
    formality: int
    warmth: str
    occasions: list[str]
    status: str  # ready | unsure | not_clothing
    confidence: float
    model: str
    alternatives: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


class TextBank:
    """Cached, template-averaged text embeddings for one model."""

    def __init__(self, emb: Embedder, vocab: Vocab) -> None:
        self.types = vocab.types
        self.patterns = list(vocab.patterns)
        names = [t.prompt or t.type for t in vocab.types]
        self.type_vecs = l2(
            np.mean([emb.text([tpl.format(n) for n in names]) for tpl in TYPE_TEMPLATES], axis=0)
        )
        self.pattern_vecs = emb.text(list(vocab.patterns.values()))
        self.clothing_vecs = emb.text([*CLOTHING_PROMPTS, *NOT_CLOTHING_PROMPTS])


def status_for(p_clothing: float, type_confidence: float) -> str:
    """not_clothing when non-clothing scenes win; unsure when the top type is below 0.35."""
    if p_clothing < 0.5:
        return "not_clothing"
    return "unsure" if type_confidence < UNSURE_BELOW else "ready"


def display_name(color: str, t: TypeEntry, palette_names: tuple[str, ...]) -> str:
    """'Navy oxford shirt'. Types that already carry a color word ('white sneakers') keep theirs."""
    first = t.type.split()[0]
    if first in {w for n in palette_names for w in n.split()} or first in {"light", "dark"}:
        return t.type[0].upper() + t.type[1:]
    return f"{color[0].upper()}{color[1:]} {t.type}"


def tag(
    crop: Image.Image,
    rgb: NDArray[np.uint8],
    mask: NDArray[np.bool_] | None,
    emb: Embedder,
    bank: TextBank,
    palette: Palette,
    image_vec: NDArray[np.float32] | None = None,
) -> tuple[Suggestions, NDArray[np.float32]]:
    vec = image_vec if image_vec is not None else emb.image([crop])[0]
    s = emb.logit_scale
    type_p = softmax(s * (bank.type_vecs @ vec))
    order = np.argsort(-type_p)
    best = bank.types[int(order[0])]
    conf = float(type_p[order[0]])
    pattern = bank.patterns[int(np.argmax(bank.pattern_vecs @ vec))]
    scene_p = softmax(s * (bank.clothing_vecs @ vec))
    p_clothing = float(scene_p[: len(CLOTHING_PROMPTS)].sum())

    primary, secondary = primary_secondary(dominant_colors(rgb, mask, palette))
    status = status_for(p_clothing, conf)
    sug = Suggestions(
        name=display_name(primary.name, best, palette.names),
        category=best.category,
        type=best.type,
        color_name=primary.name[0].upper() + primary.name[1:],
        color_hex=primary.hex,
        secondary_color=secondary.name if secondary else None,
        pattern=pattern,
        formality=best.formality,
        warmth=best.warmth,
        occasions=list(best.occasions),
        status=status,
        confidence=round(conf, 4),
        model=emb.model_id,
        alternatives=[
            {"type": bank.types[int(k)].type, "p": round(float(type_p[k]), 4)} for k in order[1:4]
        ],
    )
    return sug, vec

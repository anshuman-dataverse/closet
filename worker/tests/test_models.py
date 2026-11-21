"""Real models on the synthetic shirt fixture. Slow, downloads weights: `pytest -m models`."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

pytestmark = pytest.mark.models
FIXTURE = Path(__file__).resolve().parents[2] / "web/tests/e2e/fixtures/shirt.jpg"


@pytest.mark.parametrize("model_id", ["patrickjohncyh/fashion-clip", "Marqo/marqo-fashionSigLIP"])
def test_real_pipeline_tags_a_shirt(model_id: str) -> None:
    from closet_worker.vision.color import Palette
    from closet_worker.vision.cutout import Cutter
    from closet_worker.vision.embed import load_embedder
    from closet_worker.vision.tagger import TextBank, tag
    from closet_worker.vocab import load_vocab

    v = load_vocab()
    emb = load_embedder(model_id)
    cut = Cutter().cut(Image.open(FIXTURE))
    s, vec = tag(cut.crop, cut.rgb, cut.mask, emb, TextBank(emb, v), Palette.from_dict(v.colors))
    assert s.category in {"Tops", "Layers"}, s
    assert s.color_name.lower() in {"navy", "indigo"}, s
    assert s.status != "not_clothing"
    assert len(vec) == emb.dim
    print(model_id, s.name, s.type, round(s.confidence, 3), [a["type"] for a in s.alternatives])


@pytest.mark.models
def test_long_text_is_truncated_not_an_error() -> None:
    from closet_worker.vision.embed import FASHION_CLIP, load_embedder

    emb = load_embedder(FASHION_CLIP, "cpu")
    long = " ".join(["very long product name"] * 60)  # well past 77 tokens
    v = emb.text([long, "navy chinos"])
    assert v.shape == (2, 512)
    short = emb.text([long], max_length=64)  # type: ignore[call-arg]
    assert short.shape == (1, 512)

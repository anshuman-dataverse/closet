from __future__ import annotations

import numpy as np

from closet_worker.vision.color import Palette
from closet_worker.vision.tagger import TextBank, display_name, softmax, status_for, tag
from closet_worker.vocab import load_vocab

from .stubs import StubCutter, StubEmbedder, two_color_image

V = load_vocab()
PAL = Palette.from_dict(V.colors)


def run(emb: StubEmbedder):  # type: ignore[no-untyped-def]
    cut = StubCutter().cut(two_color_image((31, 42, 72), (31, 42, 72), 0))
    return tag(cut.crop, cut.rgb, cut.mask, emb, TextBank(emb, V), PAL)[0]


def test_softmax_sums_to_one() -> None:
    assert np.isclose(softmax(np.array([1.0, 2.0, 3.0])).sum(), 1.0)


def test_confident_tag_fills_everything_from_the_type() -> None:
    s = run(StubEmbedder("a photo of a chinos"))
    assert s.status == "ready"
    assert (s.type, s.category, s.formality, s.warmth) == ("chinos", "Bottoms", 3, "medium")
    assert s.occasions == ["office", "college"]
    assert s.color_name == "Navy" and s.name == "Navy chinos"
    assert s.confidence >= 0.35 and len(s.alternatives) == 3


def test_status_rules() -> None:
    assert status_for(0.9, 0.80) == "ready"
    assert status_for(0.9, 0.34) == "unsure"
    assert status_for(0.9, 0.35) == "ready"
    assert status_for(0.4, 0.99) == "not_clothing"


def test_flat_scores_are_low_confidence() -> None:
    s = run(StubEmbedder("a photo of a chinos", scale=1.0))
    assert s.confidence < 0.35 and s.status in {"unsure", "not_clothing"}


def test_not_clothing() -> None:
    assert run(StubEmbedder("a photo of a chinos", clothing=False)).status == "not_clothing"


def test_names_keep_color_words_already_in_the_type() -> None:
    by = {t.type: t for t in V.types}
    assert display_name("navy", by["oxford shirt"], PAL.names) == "Navy oxford shirt"
    assert display_name("navy", by["white sneakers"], PAL.names) == "White sneakers"
    assert display_name("navy", by["light wash jeans"], PAL.names) == "Light wash jeans"

"""Garment heads (vision/heads.py), their use in tag_item, and the training helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from closet_worker.jobs.tag_item import apply_heads, heads_fit
from closet_worker.vision import heads as H
from train import garment_heads as T

D = 8


def unit(i: int) -> np.ndarray:
    v = np.zeros(D, dtype=np.float32)
    v[i] = 1.0
    return v


def head(name: str, labels: list[str], scale: float = 10.0) -> H.Head:
    # Label k fires on unit(k).
    w = np.zeros((len(labels), D), dtype=np.float32)
    for k in range(len(labels)):
        w[k, k] = scale
    return H.Head(name, tuple(labels), w, np.zeros(len(labels), dtype=np.float32), 0.5)


GOOD = {"use": True, "n": 20, "accuracy": 0.9, "baseline_accuracy": 0.6}


def install(folder: Path, heads: list[H.Head], gate: dict[str, Any]) -> Path:
    H.save(folder, "fashion-clip", heads, {"gate": gate})
    return folder


def test_save_load_and_refusals(tmp_path: Path) -> None:
    f = install(tmp_path / "h", [head("type", ["jeans", "t-shirt"])], {"type": GOOD})
    h = H.load(f, "fashion-clip")
    assert h is not None and h.heads["type"].predict(unit(1))[0] == "t-shirt"
    assert H.load(tmp_path / "none") is None
    with pytest.raises(H.HeadsError, match="trained on"):
        H.load(f, "other-embedder")
    meta = json.loads((f / H.META_FILE).read_text())
    (f / H.META_FILE).write_text(json.dumps({**meta, "sha256": "0" * 64}))
    with pytest.raises(H.HeadsError, match="SHA-256"):
        H.load(f)


@pytest.mark.parametrize(
    ("gate", "ok"),
    [
        (GOOD, True),
        ({**GOOD, "use": False}, False),
        ({**GOOD, "accuracy": 0.6}, False),  # a tie with today's guess isn't a win
        ({**GOOD, "n": 3}, False),  # too few of your photos
        ({"use": True}, False),  # no numbers: a hand edit can't switch it on
    ],
)
def test_allowed_rechecks_the_gate(gate: dict[str, Any], ok: bool) -> None:
    h = H.Heads("e", {"type": head("type", ["a", "b"])}, {"type": gate})
    assert h.allowed("type", "a") is ok


def test_fit_heads_are_gated_per_label() -> None:
    gate = {
        "use": True,
        "per_label": {
            "slim": {"suggested": 8, "precision": 0.875},
            "relaxed": {"suggested": 8, "precision": 0.5},
            "wide": {"suggested": 2, "precision": 1.0},
        },
    }
    h = H.Heads(
        "e",
        {"fit/bottoms": head("fit/bottoms", ["relaxed", "slim", "wide"])},
        {"fit/bottoms": gate},
    )
    assert h.suggest("fit/bottoms", unit(1)) == "slim"
    assert h.suggest("fit/bottoms", unit(0)) is None  # right only half the time
    assert h.suggest("fit/bottoms", unit(2)) is None  # too few to trust
    flat = H.Heads(
        "e",
        {"fit/bottoms": head("fit/bottoms", ["relaxed", "slim", "wide"], 0.0)},
        {"fit/bottoms": gate},
    )
    assert flat.suggest("fit/bottoms", unit(1)) is None  # not sure enough (below min_p)


def sug() -> dict[str, Any]:
    return {
        "name": "Navy oxford shirt",
        "category": "Tops",
        "type": "oxford shirt",
        "color_name": "Navy",
        "pattern": "solid",
        "formality": 3,
        "status": "ready",
    }


def test_type_head_replaces_the_zero_shot_type() -> None:
    h = H.Heads("e", {"type": head("type", ["jeans", "t-shirt"])}, {"type": GOOD})
    s = sug()
    apply_heads(s, unit(0), h, ("navy",))
    assert (s["type"], s["category"], s["name"]) == ("jeans", "Bottoms", "Navy jeans")
    assert s["sources"] == {"type": "head", "category": "head"}


def test_category_head_clears_a_type_from_another_category() -> None:
    h = H.Heads("e", {"category": head("category", ["Bottoms", "Tops"])}, {"category": GOOD})
    s = sug()
    apply_heads(s, unit(0), h, ("navy",))
    assert (s["category"], s["type"], s["status"], s["name"]) == (
        "Bottoms",
        "",
        "unsure",
        "Navy pants",
    )


def test_closed_heads_change_nothing() -> None:
    h = H.Heads(
        "e",
        {
            "type": head("type", ["jeans", "t-shirt"]),
            "pattern": head("pattern", ["checked", "solid"]),
        },
        {"type": {**GOOD, "use": False}},
    )
    s = sug()
    apply_heads(s, unit(0), h, ("navy",))
    assert s == {**sug(), "sources": {}}


def test_heads_fit_uses_the_items_category() -> None:
    gate = {"use": True, "per_label": {"slim": {"suggested": 9, "precision": 0.9}}}
    h = H.Heads(
        "e", {"fit/bottoms": head("fit/bottoms", ["relaxed", "slim"])}, {"fit/bottoms": gate}
    )
    s = sug()
    assert (
        heads_fit(h, {"category": "Bottoms"}, s, unit(1)) == "slim"
        and s["sources"]["fit"] == "head"
    )
    assert heads_fit(h, {"category": "Shoes"}, sug(), unit(1)) is None


# ---------------------------------------------------------------- training helpers

ANN = {
    "licenses": [
        {"id": 1, "name": "Attribution License"},
        {"id": 4, "name": "Attribution-NonCommercial License"},
    ],
    "images": [
        {"id": 1, "file_name": "a.jpg", "license": 1},
        {"id": 2, "file_name": "b.jpg", "license": 4},
    ],
    "categories": [
        {"id": 6, "name": "pants"},
        {"id": 1, "name": "top, t-shirt, sweatshirt"},
        {"id": 31, "name": "sleeve"},
    ],
    "attributes": [
        {"id": 1, "name": "jeans", "supercategory": "nickname"},
        {"id": 2, "name": "loose (fit)", "supercategory": "silhouette"},
        {"id": 3, "name": "wide leg", "supercategory": "silhouette"},
        {"id": 4, "name": "plain (pattern)", "supercategory": "textile pattern"},
        {"id": 5, "name": "stripe", "supercategory": "textile pattern"},
        {"id": 6, "name": "short (length)", "supercategory": "length"},
        {"id": 7, "name": "classic (t-shirt)", "supercategory": "nickname"},
    ],
    "annotations": [
        {
            "image_id": 1,
            "category_id": 6,
            "attribute_ids": [1, 2, 3, 4],
            "bbox": [0, 0, 10, 20],
            "segmentation": [[0, 0, 10, 0, 10, 20]],
        },
        {
            "image_id": 1,
            "category_id": 1,
            "attribute_ids": [4, 5, 7],
            "bbox": [0, 0, 20, 20],
            "segmentation": [],
        },
        {"image_id": 1, "category_id": 31, "attribute_ids": [6], "bbox": [1, 1, 4, 4]},
        {"image_id": 2, "category_id": 6, "attribute_ids": [1], "bbox": [0, 0, 5, 5]},
    ],
}


def test_fashionpedia_mapping() -> None:
    ex = T.fashionpedia_examples(ANN)
    pants, tee, nc = ex
    assert pants.labels == {
        "category": "Bottoms",
        "type": "jeans",
        "pattern": "solid",
        "fit/bottoms": "wide",
    }
    assert tee.labels == {
        "category": "Tops",
        "type": "t-shirt",
        "sleeve": "short",
    }  # plain + stripe disagree
    assert nc.license == "Attribution-NonCommercial License"
    assert len(T.fashionpedia_examples(ANN, commercial_only=True)) == 2


def test_cc0_mapping_and_grouped_split() -> None:
    rows = [
        {"image": f"i{k}", "sender_id": str(k % 7), "label": "T-Shirt", "kids": "False"}
        for k in range(70)
    ]
    rows += [
        {"image": "kid", "sender_id": "1", "label": "Pants", "kids": "True"},
        {"image": "x", "sender_id": "2", "label": "Not sure", "kids": "False"},
    ]
    ex = T.cc0_examples(rows)
    assert len(ex) == 70 and ex[0].labels == {"category": "Tops", "type": "t-shirt"}
    tr, te = T.split_by_group(ex, 0.3)
    assert {ex[i].group for i in tr}.isdisjoint({ex[i].group for i in te}) and te


def test_masks() -> None:
    m = T.polygon_mask([[0, 0, 9, 0, 9, 9, 0, 9]], (20, 20))
    assert m[5, 5] and not m[15, 15]
    # counts alternate off/on, column-major: 1 off, 2 on, 3 off over a 2x3 image
    r = T.rle_mask({"size": [2, 3], "counts": [1, 2, 3]})
    assert r.tolist() == [[False, True, False], [True, False, False]]


def test_train_head_learns_and_drops_rare_labels() -> None:
    rng = np.random.default_rng(0)
    x = np.concatenate(
        [
            unit(0) + 0.1 * rng.standard_normal((60, D)),
            unit(1) + 0.1 * rng.standard_normal((60, D)),
            unit(2) + 0.1 * rng.standard_normal((5, D)),
        ]
    ).astype(np.float32)
    y = ["a"] * 60 + ["b"] * 60 + ["c"] * 5
    t = T.train_head("x", x, y, x, y, min_per_label=30)
    assert t is not None and t.labels == ["a", "b"] and t.report["dropped_too_few"] == {"c": 5}
    assert t.report["test_accuracy"] == 1.0


def test_gate_against_baseline() -> None:
    truth = ["a", "a", "b", "b", "b", "a"]
    g = T.gate_against_baseline(
        ["a", "a", "b", "b", "b", "b"], ["a", "b", "b", "a", "b", "b"], truth, False
    )
    assert g["use"] and g["accuracy"] > g["baseline_accuracy"]
    worse = T.gate_against_baseline(["b"] * 6, truth, truth, False)
    assert not worse["use"] and "didn’t beat" in worse["why"]
    assert not T.gate_against_baseline([], [], [], False)["use"]


def test_two_label_head_matches_sklearn() -> None:
    from closet_worker.vision.heads import Head

    rng = np.random.default_rng(1)
    x = np.concatenate(
        [unit(0) + 0.3 * rng.standard_normal((50, D)), unit(1) + 0.3 * rng.standard_normal((50, D))]
    ).astype(np.float32)
    y = ["long"] * 50 + ["short"] * 50
    t = T.train_head("sleeve", x, y, x, y, min_per_label=10)
    assert t is not None and t.w.shape == (2, D) and t.b.shape == (2,)
    from sklearn.linear_model import LogisticRegression

    ref = LogisticRegression(C=t.c, max_iter=3000, class_weight="balanced").fit(x, y)
    h = Head("sleeve", tuple(t.labels), t.w, t.b, 0.0)
    ours = np.array([h.probs(v)[1] for v in x])
    assert np.allclose(ours, ref.predict_proba(x)[:, 1], atol=1e-5)

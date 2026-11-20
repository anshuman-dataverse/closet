"""Tagging eval (SPEC 5.1): accuracy of each fashion CLIP model on your hand-checked photos.

Usage (Mac or Colab):
    python -m eval.tagging --data ~/ClosetPhotos/eval [--models A B] [--no-cutout] [--device auto]

`--data` holds `labels.csv` (file, item_name, category, type, pattern, color) and `photos/`.
Writes report.json (and confusion_<model>.png when matplotlib is available) into --data.
Targets: category ≥ 90%, type ≥ 70%.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FIELDS = ("category", "type", "pattern", "color")
TARGETS = {"category": 0.90, "type": 0.70}


def norm(s: str | None) -> str:
    return " ".join((s or "").strip().lower().replace("-", " ").split())


@dataclass
class Row:
    file: str
    truth: dict[str, str]


def read_labels(path: Path) -> list[Row]:
    rows: list[Row] = []
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            if not (r.get("file") or "").strip():
                continue
            rows.append(Row(r["file"].strip(), {k: norm(r.get(k)) for k in FIELDS}))
    return rows


def accuracy(truth: Sequence[str], pred: Sequence[str]) -> tuple[float, int]:
    """Share of rows where pred matches truth, skipping rows with no label. Returns (acc, n)."""
    pairs = [(t, p) for t, p in zip(truth, pred, strict=True) if t]
    if not pairs:
        return 0.0, 0
    return sum(t == p for t, p in pairs) / len(pairs), len(pairs)


def confusion(truth: Sequence[str], pred: Sequence[str]) -> tuple[list[str], list[list[int]]]:
    labels = sorted({t for t in truth if t} | {p for t, p in zip(truth, pred, strict=True) if t})
    ix = {label: i for i, label in enumerate(labels)}
    m = [[0] * len(labels) for _ in labels]
    for t, p in zip(truth, pred, strict=True):
        if t:
            m[ix[t]][ix[p]] += 1
    return labels, m


def score(rows: list[Row], preds: list[dict[str, str]]) -> dict[str, Any]:
    out: dict[str, Any] = {"n": len(rows), "accuracy": {}, "labeled": {}}
    for k in FIELDS:
        acc, n = accuracy([r.truth[k] for r in rows], [norm(p.get(k)) for p in preds])
        out["accuracy"][k] = round(acc, 4)
        out["labeled"][k] = n
    out["targets_met"] = all(out["accuracy"][k] >= v for k, v in TARGETS.items())
    out["type_confusion"] = confusion(
        [r.truth["type"] for r in rows], [norm(p.get("type")) for p in preds]
    )
    return out


def recommend(report: dict[str, dict[str, Any]]) -> str:
    """Best model by mean of category and type accuracy."""
    return max(
        report, key=lambda m: report[m]["accuracy"]["category"] + report[m]["accuracy"]["type"]
    )


def _plot(labels: list[str], m: list[list[int]], title: str, out: Path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    size = max(6.0, 0.35 * len(labels))
    fig, ax = plt.subplots(figsize=(size, size))
    ax.imshow(m, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels, rotation=90, fontsize=7)
    ax.set_yticks(range(len(labels)), labels, fontsize=7)
    ax.set_xlabel("predicted")
    ax.set_ylabel("label")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


def run(
    data: Path, models: Sequence[str], cutout: bool = True, device: str = "auto"
) -> dict[str, Any]:
    import numpy as np
    from PIL import Image

    from closet_worker.vision.color import Palette
    from closet_worker.vision.cutout import Cutter, compose
    from closet_worker.vision.embed import load_embedder
    from closet_worker.vision.tagger import TextBank, tag
    from closet_worker.vocab import load_vocab

    rows = read_labels(data / "labels.csv")
    vocab = load_vocab()
    palette = Palette.from_dict(vocab.colors)
    cutter = Cutter() if cutout else None
    cuts = []
    for r in rows:
        img = Image.open(data / "photos" / r.file).convert("RGB")
        cuts.append(
            cutter.cut(img) if cutter else compose(img, np.ones(img.size[::-1], dtype=bool))
        )

    unknown_types = sorted(
        {r.truth["type"] for r in rows if r.truth["type"]} - {norm(t.type) for t in vocab.types}
    )
    report: dict[str, dict[str, Any]] = {}
    for model_id in models:
        emb = load_embedder(model_id, device)
        bank = TextBank(emb, vocab)
        preds = []
        for c in cuts:
            s, _ = tag(c.crop, c.rgb, c.mask, emb, bank, palette)
            preds.append(
                {
                    "category": s.category,
                    "type": s.type,
                    "pattern": s.pattern,
                    "color": s.color_name,
                }
            )
        report[model_id] = score(rows, preds)
        report[model_id]["predictions"] = [
            {"file": r.file, **p} for r, p in zip(rows, preds, strict=True)
        ]
        labels, m = report[model_id]["type_confusion"]
        _plot(
            labels,
            m,
            f"Type confusion: {model_id}",
            data / f"confusion_{model_id.replace('/', '_')}.png",
        )

    best = recommend(report)
    result = {
        "models": report,
        "recommended": best,
        "targets": TARGETS,
        "types_not_in_vocab": unknown_types,
    }
    (data / "report.json").write_text(json.dumps(result, indent=2))
    return result


def print_table(result: dict[str, Any]) -> None:
    print(f"{'model':32} {'n':>4} " + " ".join(f"{k:>9}" for k in FIELDS) + "  targets")
    for m, r in result["models"].items():
        accs = " ".join(f"{r['accuracy'][k] * 100:8.1f}%" for k in FIELDS)
        print(f"{m:32} {r['n']:>4} {accs}  {'met' if r['targets_met'] else 'missed'}")
    print(f"\nRecommended EMBED_MODEL={result['recommended']}")
    if result["types_not_in_vocab"]:
        print(
            "Labels with types not in vocab/types.yaml (always count as wrong):",
            ", ".join(result["types_not_in_vocab"]),
        )


def main() -> None:
    from closet_worker.vision.embed import MODELS

    p = argparse.ArgumentParser(prog="eval.tagging")
    p.add_argument("--data", default="~/ClosetPhotos/eval")
    p.add_argument("--models", nargs="+", default=list(MODELS))
    p.add_argument("--no-cutout", action="store_true")
    p.add_argument("--device", default="auto")
    a = p.parse_args()
    print_table(run(Path(a.data).expanduser(), a.models, cutout=not a.no_cutout, device=a.device))


if __name__ == "__main__":
    main()

"""Tagging eval (SPEC 5.1): accuracy of each fashion CLIP model on your hand-checked photos.

Usage (Mac or Colab):
    python -m eval.tagging --data ~/ClosetPhotos/eval [--models A B] [--no-cutout] [--device auto]

`--data` holds `labels.csv` (file, item_name, category, type, pattern, color, fit) and `photos/`.
Writes report.json (and confusion_<model>.png when matplotlib is available) into --data, plus
closet-fit-results.zip for `closet-worker import` (which fits are reliable enough to suggest).
Targets: category ≥ 90%, type ≥ 70%. Fit: a fit is suggested only if it was right ≥ 70% of the
times it was guessed, over ≥ 5 guesses (vocab/fits.yaml `gate`).
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
CATEGORY_BY_NORM = {
    c.lower(): c for c in ("Tops", "Bottoms", "Layers", "Shoes", "Accessories", "Sets & suits")
}
TARGETS = {"category": 0.90, "type": 0.70}


def norm(s: str | None) -> str:
    return " ".join((s or "").strip().lower().replace("-", " ").split())


@dataclass
class Row:
    file: str
    truth: dict[str, str]


FIT_SYNONYMS = {
    "baggy": "wide",
    "wide leg": "wide",
    "wide or baggy": "wide",
    "flared": "flare",
    "oversize": "oversized",
    "regular fit": "regular",
    "slim fit": "slim",
    "straight leg": "straight",
    "a line": "a-line",
}


def norm_fit(s: str | None) -> str:
    """Your fit label as a fit id: ids, labels ("Wide or baggy") and a few common words."""
    t = norm(s)
    return FIT_SYNONYMS.get(t, t)


def read_labels(path: Path) -> list[Row]:
    rows: list[Row] = []
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            if not (r.get("file") or "").strip():
                continue
            truth = {k: norm(r.get(k)) for k in FIELDS}
            truth["fit"] = norm_fit(r.get("fit"))
            rows.append(Row(r["file"].strip(), truth))
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


def fit_report(cases: list[dict[str, Any]], min_precision: float, min_n: int) -> dict[str, Any]:
    """cases: {truth, guess, photo, group} per labeled piece (fit ids; guess may be None).

    per_fit precision = right / guessed for that fit: "when it says flared, how often is it?"
    """
    per: dict[str, dict[str, Any]] = {}
    for c in cases:
        for key in {
            f"{c['group']}/{c['truth']}",
            *([f"{c['group']}/{c['guess']}"] if c["guess"] else []),
        }:
            per.setdefault(key, {"labeled": 0, "suggested": 0, "right": 0})
        per[f"{c['group']}/{c['truth']}"]["labeled"] += 1
        if c["guess"]:
            g = per[f"{c['group']}/{c['guess']}"]
            g["suggested"] += 1
            g["right"] += c["guess"] == c["truth"]
    for r in per.values():
        r["precision"] = round(r["right"] / r["suggested"], 4) if r["suggested"] else 0.0
        r["passes"] = r["suggested"] >= min_n and r["precision"] >= min_precision
    guessed = [c for c in cases if c["guess"]]
    return {
        "n_labeled": len(cases),
        "coverage": round(len(guessed) / len(cases), 4) if cases else 0.0,
        "accuracy_when_guessed": round(
            sum(c["guess"] == c["truth"] for c in guessed) / len(guessed), 4
        )
        if guessed
        else 0.0,
        "photo_model_top1": round(sum(c["photo"] == c["truth"] for c in cases) / len(cases), 4)
        if cases
        else 0.0,
        "per_fit": dict(sorted(per.items())),
        "measurements": _measurements(cases),
    }


def _measurements(cases: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Median outline ratios per labeled fit, to tune the thresholds in vision/fit.py honestly."""
    import statistics

    by: dict[str, list[dict[str, float]]] = {}
    for c in cases:
        if c.get("features"):
            by.setdefault(f"{c['group']}/{c['truth']}", []).append(c["features"])
    return {
        k: {f: round(statistics.median(x[f] for x in v), 3) for f in v[0]} | {"n": float(len(v))}
        for k, v in sorted(by.items())
    }


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
    data: Path,
    models: Sequence[str],
    cutout: bool = True,
    device: str = "auto",
    wears: str | None = None,
) -> dict[str, Any]:
    import numpy as np
    from PIL import Image

    from closet_worker.vision.color import Palette
    from closet_worker.vision.cutout import Cutter, compose
    from closet_worker.vision.embed import load_embedder
    from closet_worker.vision.fit import guess_fit, load_fits
    from closet_worker.vision.tagger import TextBank, tag
    from closet_worker.vocab import load_vocab

    rows = read_labels(data / "labels.csv")
    meta = json.loads((data / "meta.json").read_text()) if (data / "meta.json").exists() else {}
    wears = wears or meta.get("wears")
    fv = load_fits()
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
        fit_cases: list[dict[str, Any]] = []
        for r, c in zip(rows, cuts, strict=True):
            s, vec = tag(c.crop, c.rgb, c.mask, emb, bank, palette)
            cat = CATEGORY_BY_NORM.get(r.truth["category"]) or s.category
            g = fv.group_for(cat)
            if r.truth["fit"] and g is not None:
                fg = guess_fit(vec, c.mask, cat, r.truth["type"] or s.type, wears, emb)
                if fg is not None:
                    fit_cases.append(
                        {
                            "file": r.file,
                            "group": g.name,
                            "truth": r.truth["fit"],
                            "guess": fg.fit,
                            "photo": fg.photo_fit,
                            "method": fg.method,
                            "shape": fg.shape,
                            "features": fg.features,
                        }
                    )
            preds.append(
                {
                    "category": s.category,
                    "type": s.type,
                    "pattern": s.pattern,
                    "color": s.color_name,
                }
            )
        report[model_id] = score(rows, preds)
        report[model_id]["fit"] = fit_report(fit_cases, fv.min_precision, fv.min_n)
        report[model_id]["fit_cases"] = fit_cases
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
    known_fits = {f.id for g in fv.groups for f in g.fits}
    result["fits_not_in_vocab"] = sorted(
        {r.truth["fit"] for r in rows if r.truth["fit"]} - known_fits
    )
    (data / "report.json").write_text(json.dumps(result, indent=2))
    write_fit_results(data, result, best, wears)
    return result


def write_fit_results(data: Path, result: dict[str, Any], model: str, wears: str | None) -> Path:
    """fit_gate.json (for the model the Mac should use) + report.json, zipped for import."""
    from datetime import UTC, datetime

    from closet_worker.bundle import write_bundle

    fr = result["models"][model]["fit"]
    gate = {
        "model": model,
        "wears": wears,
        "measured_at": datetime.now(UTC).isoformat(),
        "n_labeled": fr["n_labeled"],
        "per_fit": {k: v for k, v in fr["per_fit"].items() if v["suggested"]},
    }
    (data / "fit_gate.json").write_text(json.dumps(gate, indent=2) + "\n")
    return write_bundle(
        "fit_gate",
        {"fit_gate.json": data / "fit_gate.json", "report.json": data / "report.json"},
        data / "closet-fit-results.zip",
    )


def print_table(result: dict[str, Any]) -> None:
    print(f"{'model':32} {'n':>4} " + " ".join(f"{k:>9}" for k in FIELDS) + "  targets")
    for m, r in result["models"].items():
        accs = " ".join(f"{r['accuracy'][k] * 100:8.1f}%" for k in FIELDS)
        print(f"{m:32} {r['n']:>4} {accs}  {'met' if r['targets_met'] else 'missed'}")
    print(f"\nRecommended EMBED_MODEL={result['recommended']}")
    for m, r in result["models"].items():
        f = r["fit"]
        if not f["n_labeled"]:
            print(f"{m}: no fit labels yet (fill the fit column in labels.csv)")
            continue
        print(
            f"\nFit, {m}: {f['n_labeled']} labeled, guessed {f['coverage'] * 100:.0f}% of them, "
            f"right {f['accuracy_when_guessed'] * 100:.0f}% when it guessed "
            f"(photo model alone: {f['photo_model_top1'] * 100:.0f}%)"
        )
        for k, v in f["per_fit"].items():
            if v["suggested"] or v["labeled"]:
                mark = "on" if v["passes"] else "off"
                print(
                    f"  {k:22} labeled {v['labeled']:>3}  guessed {v['suggested']:>3}  "
                    f"right {v['right']:>3}  ({v['precision'] * 100:.0f}%)  {mark}"
                )
    if result.get("fits_not_in_vocab"):
        print(
            "Fit labels not in vocab/fits.yaml (skipped):", ", ".join(result["fits_not_in_vocab"])
        )
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
    p.add_argument("--wears", choices=["menswear", "womenswear", "both"], default=None)
    a = p.parse_args()
    data = Path(a.data).expanduser()
    print_table(run(data, a.models, cutout=not a.no_cutout, device=a.device, wears=a.wears))
    print(f"\nFor the Mac: closet-worker import {data / 'closet-fit-results.zip'}")


if __name__ == "__main__":
    main()

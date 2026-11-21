"""Train garment heads (category, type, pattern, fit) on FashionCLIP embeddings.

Data (personal, non-commercial use: the owner and one other person):
- Fashionpedia (Jia et al., ECCV 2020): annotations CC BY 4.0. Photos carry their own licenses,
  many non-commercial; `commercial_only=True` keeps only CC BY, public domain, Unsplash, Pexels
  and freestocks. Each garment is cut out with its segmentation mask onto white, like Closet's.
- Clothing dataset (Grigorev et al.), CC0 1.0: phone photos of real clothes. Split by sender, so
  one person's photos are never in both train and test.

Labels map onto Closet's own vocabulary (types.yaml, patterns.yaml, fits.yaml). Anything that
doesn't map cleanly is left out rather than guessed. Heads are plain logistic regressions.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

# Fashionpedia image licenses that allow commercial use (ids from its "licenses" table).
COMMERCIAL_OK = {
    "Attribution License",
    "Public Domain Dedication",
    "unsplash",
    "pexels",
    "freestocks",
}

FP_CATEGORY = {
    "shirt, blouse": "Tops",
    "top, t-shirt, sweatshirt": "Tops",
    "sweater": "Layers",
    "cardigan": "Layers",
    "jacket": "Layers",
    "vest": "Layers",
    "coat": "Layers",
    "pants": "Bottoms",
    "shorts": "Bottoms",
    "skirt": "Bottoms",
    "dress": "Sets & suits",
    "jumpsuit": "Sets & suits",
    "shoe": "Shoes",
    "bag, wallet": "Accessories",
    "belt": "Accessories",
    "watch": "Accessories",
    "scarf": "Accessories",
    "tie": "Accessories",
    "glasses": "Accessories",
    "hat": "Accessories",
}
# Fit group for Closet's fits.yaml.
FP_FIT_GROUP = {
    "shirt, blouse": "tops",
    "top, t-shirt, sweatshirt": "tops",
    "sweater": "tops",
    "cardigan": "tops",
    "jacket": "tops",
    "vest": "tops",
    "coat": "tops",
    "pants": "bottoms",
}
# Fashionpedia silhouette → Closet fit id, per group. "tight (fit)" pants can be skinny or slim;
# Closet calls it slim. Peg, pencil, curved and others have no clean match and are left out.
FP_FIT = {
    "tops": {
        "tight (fit)": "slim",
        "regular (fit)": "regular",
        "loose (fit)": "relaxed",
        "oversized": "oversized",
    },
    "bottoms": {
        "tight (fit)": "slim",
        "regular (fit)": "straight",
        "straight": "straight",
        "loose (fit)": "relaxed",
        "wide leg": "wide",
        "baggy": "wide",
        "bootcut": "bootcut",
        "flare": "flare",
        "bell bottom": "flare",
    },
}
# Sleeve length, from the "sleeve" part annotations attached to their garment.
FP_SLEEVE = {
    "sleeveless": "sleeveless",
    "short (length)": "short",
    "elbow-length": "short",
    "three quarter (length)": "long",
    "wrist-length": "long",
}
SLEEVED = {"shirt, blouse", "top, t-shirt, sweatshirt", "sweater", "cardigan", "jacket", "coat"}

# A garment often carries two silhouettes ("loose (fit)" + "wide leg"; "tight (fit)" + "straight").
# The more specific shape wins: loose + wide leg is wide, tight + straight is slim.
FIT_PRIORITY = {
    "tops": ("oversized", "relaxed", "slim", "regular"),
    "bottoms": ("flare", "bootcut", "wide", "relaxed", "slim", "straight"),
}

# Fashionpedia nickname (or category + detail) → a type in Closet's types.yaml.
FP_TYPE = {
    "classic (t-shirt)": "t-shirt",
    "polo (shirt)": "polo shirt",
    "henley (shirt)": "henley",
    "rugby (shirt)": "rugby shirt",
    "tank (top)": "tank top",
    "hoodie": "hoodie",
    "blazer": "blazer",
    "bomber (jacket)": "bomber jacket",
    "puffer (jacket)": "puffer jacket",
    "puffer (coat)": "puffer jacket",
    "varsity (jacket)": "varsity jacket",
    "nehru (jacket)": "nehru jacket",
    "trench (coat)": "trench coat",
    "raincoat": "rain jacket",
    "jeans": "jeans",
    "sweatpants": "sweatpants",
    "cargo (pants)": "cargo trousers",
    "track (pants)": "track pants",
}
FP_TYPE_BY_CATEGORY = {
    "cardigan": "cardigan",
    "vest": "vest",
    "shorts": "shorts",
    "tie": "tie",
    "belt": "belt",
    "watch": "watch",
    "scarf": "scarf",
}
FP_SWEATER_NECK = {
    "v-neck": "v-neck sweater",
    "crew (neck)": "crew neck sweater",
    "round (neck)": "crew neck sweater",
    "turtle (neck)": "turtleneck",
}
FP_PATTERN = {
    "plain (pattern)": "solid",
    "stripe": "striped",
    "check": "checked",
    "houndstooth (pattern)": "checked",
    "herringbone (pattern)": "textured",
    "chevron": "printed",
    "floral": "printed",
    "abstract": "printed",
    "geometric": "printed",
    "paisley": "printed",
    "dot": "printed",
    "cartoon": "printed",
    "letters": "printed",
    "numbers": "printed",
    "camouflage": "printed",
    "fair isle": "printed",
    "argyle": "printed",
    "leopard": "printed",
    "zebra": "printed",
    "cheetah": "printed",
    "snakeskin (pattern)": "printed",
}
# Clothing dataset (CC0) labels → (Closet category, Closet type or None).
CC0_LABELS: dict[str, tuple[str, str | None]] = {
    "T-Shirt": ("Tops", "t-shirt"),
    "Longsleeve": ("Tops", "long-sleeve t-shirt"),
    "Polo": ("Tops", "polo shirt"),
    "Shirt": ("Tops", None),
    "Hoodie": ("Layers", "hoodie"),
    "Blazer": ("Layers", "blazer"),
    "Outwear": ("Layers", None),
    "Pants": ("Bottoms", None),
    "Shorts": ("Bottoms", "shorts"),
    "Skirt": ("Bottoms", None),
    "Dress": ("Sets & suits", None),
    "Shoes": ("Shoes", None),
    "Hat": ("Accessories", None),
}


@dataclass
class Example:
    source: str  # fashionpedia | cc0
    image: str  # file name
    group: str  # for splitting: image id (Fashionpedia) or sender id (CC0)
    labels: dict[str, str]  # category, type, pattern, fit/<group>
    segmentation: Any = None
    bbox: list[float] | None = None
    license: str = ""


def _first(order: Sequence[str], values: Iterable[str]) -> str | None:
    s = set(values)
    return next((v for v in order if v in s), None)


def _one(values: Iterable[str]) -> str | None:
    """The single value, or None if there are none or they disagree."""
    s = set(values)
    return next(iter(s)) if len(s) == 1 else None


def _inside(inner: list[float], outer: list[float]) -> float:
    """Share of the inner box (x, y, w, h) that lies inside the outer box."""
    x0, y0 = max(inner[0], outer[0]), max(inner[1], outer[1])
    x1 = min(inner[0] + inner[2], outer[0] + outer[2])
    y1 = min(inner[1] + inner[3], outer[1] + outer[3])
    area = inner[2] * inner[3]
    return max(0.0, x1 - x0) * max(0.0, y1 - y0) / area if area > 0 else 0.0


def fashionpedia_examples(ann: dict[str, Any], commercial_only: bool = False) -> list[Example]:
    lic = {x["id"]: x["name"] for x in ann.get("licenses", [])}
    imgs = {i["id"]: i for i in ann["images"]}
    cats = {c["id"]: c["name"] for c in ann["categories"]}
    atts = {a["id"]: (a["name"], a["supercategory"]) for a in ann["attributes"]}
    sleeves: dict[int, list[tuple[list[float], str]]] = defaultdict(list)
    for a in ann["annotations"]:
        if cats[a["category_id"]] != "sleeve":
            continue
        ls = {
            FP_SLEEVE[atts[x][0]] for x in a.get("attribute_ids") or [] if atts[x][0] in FP_SLEEVE
        }
        if len(ls) == 1 and a.get("bbox"):
            sleeves[a["image_id"]].append((a["bbox"], ls.pop()))
    out: list[Example] = []
    for a in ann["annotations"]:
        img = imgs.get(a["image_id"])
        if img is None:
            continue
        lname = lic.get(img.get("license"), "")
        if commercial_only and lname not in COMMERCIAL_OK:
            continue
        cname = cats[a["category_id"]]
        category = FP_CATEGORY.get(cname)
        if category is None:
            continue
        by_super: dict[str, list[str]] = defaultdict(list)
        for x in a.get("attribute_ids") or []:
            n, sup = atts[x]
            by_super[sup].append(n)
        labels = {"category": category}
        t = _one(FP_TYPE[n] for n in by_super["nickname"] if n in FP_TYPE)
        if t is None and cname in FP_TYPE_BY_CATEGORY:
            t = FP_TYPE_BY_CATEGORY[cname]
        if t is None and cname == "sweater":
            t = _one(FP_SWEATER_NECK[n] for n in by_super["neckline type"] if n in FP_SWEATER_NECK)
        if t:
            labels["type"] = t
        pats = [*by_super["textile pattern"], *by_super["animal"]]
        p = _one(FP_PATTERN[n] for n in pats if n in FP_PATTERN)
        if p:
            labels["pattern"] = p
        if cname in SLEEVED and a.get("bbox"):
            own = {ln for b, ln in sleeves.get(a["image_id"], []) if _inside(b, a["bbox"]) >= 0.8}
            if "sleeveless" in by_super["length"]:
                own.add("sleeveless")
            if len(own) == 1:
                labels["sleeve"] = own.pop()
        g = FP_FIT_GROUP.get(cname)
        if g:
            f = _first(
                FIT_PRIORITY[g], (FP_FIT[g][n] for n in by_super["silhouette"] if n in FP_FIT[g])
            )
            if f:
                labels[f"fit/{g}"] = f
        out.append(
            Example(
                "fashionpedia",
                img["file_name"],
                f"fp{img['id']}",
                labels,
                a.get("segmentation"),
                a.get("bbox"),
                lname,
            )
        )
    return out


def cc0_examples(rows: Iterable[dict[str, str]]) -> list[Example]:
    out = []
    for r in rows:
        m = CC0_LABELS.get(r.get("label", ""))
        if m is None or str(r.get("kids", "")).lower() == "true":
            continue
        labels = {"category": m[0]}
        if m[1]:
            labels["type"] = m[1]
        out.append(
            Example("cc0", f"{r['image']}.jpg", f"cc0{r['sender_id']}", labels, license="CC0")
        )
    return out


def split_by_group(
    examples: Sequence[Example], test_share: float = 0.15, seed: int = 42
) -> tuple[list[int], list[int]]:
    """Train/test indices. All examples of one image or one sender stay on the same side."""
    groups = sorted({e.group for e in examples})
    rng = random.Random(seed)
    rng.shuffle(groups)
    test_groups = set(groups[: int(len(groups) * test_share)])
    tr = [i for i, e in enumerate(examples) if e.group not in test_groups]
    te = [i for i, e in enumerate(examples) if e.group in test_groups]
    return tr, te


# ---------------------------------------------------------------- crops


def polygon_mask(seg: list[list[float]], size: tuple[int, int]) -> NDArray[np.bool_]:
    from PIL import Image, ImageDraw

    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    for poly in seg:
        if len(poly) >= 6:
            d.polygon([(poly[i], poly[i + 1]) for i in range(0, len(poly), 2)], fill=1)
    return np.asarray(m, dtype=bool)


def rle_mask(seg: dict[str, Any]) -> NDArray[np.bool_]:
    """COCO RLE (compressed needs pycocotools; uncompressed counts are decoded here)."""
    h, w = seg["size"]
    counts = seg["counts"]
    if isinstance(counts, str):
        from pycocotools import mask as cocomask

        return np.asarray(cocomask.decode(seg), dtype=bool)
    flat = np.zeros(h * w, dtype=bool)
    pos, val = 0, False
    for c in counts:
        flat[pos : pos + c] = val
        pos += c
        val = not val
    return flat.reshape((w, h)).T  # column-major


def garment_crop(img: Any, ex: Example, pad: float = 0.05, min_side: int = 48) -> Any | None:
    """The garment on white, cropped to its padded mask box, like Closet's cut-outs."""
    from PIL import Image

    from closet_worker.vision.cutout import mask_bbox

    rgb = img.convert("RGB")
    seg = ex.segmentation
    if isinstance(seg, list):
        mask = polygon_mask(seg, rgb.size)
    elif isinstance(seg, dict):
        mask = rle_mask(seg)
    else:
        return rgb  # CC0 photos: the whole photo
    if mask.sum() < min_side * min_side / 2:
        return None
    box = mask_bbox(mask, pad)
    if box[2] - box[0] < min_side or box[3] - box[1] < min_side:
        return None
    white = Image.new("RGB", rgb.size, (255, 255, 255))
    white.paste(rgb, mask=Image.fromarray((mask * 255).astype(np.uint8), "L"))
    return white.crop(box)


# ---------------------------------------------------------------- training and measuring


@dataclass
class Trained:
    name: str
    labels: list[str]
    w: NDArray[np.float32]
    b: NDArray[np.float32]
    c: float
    report: dict[str, Any] = field(default_factory=dict)


def per_label(y_true: Sequence[str], y_pred: Sequence[str | None]) -> dict[str, dict[str, Any]]:
    """For each label: how many had it, how many times it was suggested, how many were right."""
    out: dict[str, dict[str, Any]] = {}
    for t, p in zip(y_true, y_pred, strict=True):
        out.setdefault(t, {"labeled": 0, "suggested": 0, "right": 0})["labeled"] += 1
        if p is not None:
            r = out.setdefault(p, {"labeled": 0, "suggested": 0, "right": 0})
            r["suggested"] += 1
            r["right"] += p == t
    for r in out.values():
        r["precision"] = round(r["right"] / r["suggested"], 4) if r["suggested"] else 0.0
        r["recall"] = round(r["right"] / r["labeled"], 4) if r["labeled"] else 0.0
    return dict(sorted(out.items()))


def train_head(
    name: str,
    x_tr: NDArray[np.float32],
    y_tr: Sequence[str],
    x_te: NDArray[np.float32],
    y_te: Sequence[str],
    min_per_label: int = 30,
    cs: Sequence[float] = (0.3, 1.0, 3.0, 10.0),
) -> Trained | None:
    """Logistic regression, class-balanced. Labels with < min_per_label training examples are
    dropped (reported), since a handful of examples can't be trusted. C is picked on a slice of
    the training data; the test split is only used once, for the report."""
    from sklearn.linear_model import LogisticRegression

    counts = Counter(y_tr)
    keep = sorted(k for k, v in counts.items() if v >= min_per_label)
    dropped = {k: v for k, v in counts.items() if v < min_per_label}
    if len(keep) < 2:
        return None
    tr = [i for i, y in enumerate(y_tr) if y in keep]
    te = [i for i, y in enumerate(y_te) if y in keep]
    xt, yt = x_tr[tr], [y_tr[i] for i in tr]
    rng = np.random.default_rng(0)
    order = rng.permutation(len(tr))
    cut = int(len(order) * 0.85)
    fit_i, val_i = order[:cut], order[cut:]

    def model(c: float) -> Any:
        return LogisticRegression(C=c, max_iter=3000, class_weight="balanced")

    best_c, best_acc = cs[0], -1.0
    for c in cs:
        m = model(c).fit(xt[fit_i], [yt[i] for i in fit_i])
        acc = float(np.mean(m.predict(xt[val_i]) == np.array([yt[i] for i in val_i])))
        if acc > best_acc:
            best_c, best_acc = c, acc
    m = model(best_c).fit(xt, yt)
    labels = [str(x) for x in m.classes_]
    pred = [str(p) for p in m.predict(x_te[te])] if te else []
    truth = [y_te[i] for i in te]
    report = {
        "train_counts": {k: counts[k] for k in keep},
        "dropped_too_few": dropped,
        "test_n": len(te),
        "test_accuracy": round(float(np.mean(np.array(pred) == np.array(truth))), 4)
        if te
        else None,
        "test_per_label": per_label(truth, pred) if te else {},
        "C": best_c,
    }
    w = np.asarray(m.coef_, dtype=np.float32)
    b = np.asarray(m.intercept_, dtype=np.float32)
    if len(labels) == 2 and w.shape[0] == 1:
        # Two labels: sklearn keeps one row (sigmoid). softmax([0, z]) == sigmoid(z) for label 1.
        w = np.vstack([np.zeros_like(w), w])
        b = np.concatenate([np.zeros_like(b), b])
    return Trained(name, labels, w, b, best_c, report)


def gate_against_baseline(
    head_preds: Sequence[str | None],
    baseline_preds: Sequence[str | None],
    truth: Sequence[str],
    is_fit: bool,
) -> dict[str, Any]:
    """Your photos decide. Non-fit heads: used only if more accurate than today's guess.
    Fit heads: per label, right ≥70% of the times it's suggested over ≥5 suggestions."""
    n = len(truth)
    if n == 0:
        return {"use": False, "n": 0, "why": "no labeled photos of yours for this head"}
    acc = sum(p == t for p, t in zip(head_preds, truth, strict=True)) / n
    base = sum(p == t for p, t in zip(baseline_preds, truth, strict=True)) / n
    g: dict[str, Any] = {
        "n": n,
        "accuracy": round(acc, 4),
        "baseline_accuracy": round(base, 4),
    }
    if is_fit:
        g["per_label"] = per_label(truth, head_preds)
        g["use"] = any(
            r["suggested"] >= 5 and r["precision"] >= 0.7 for r in g["per_label"].values()
        )
    else:
        g["use"] = n >= 5 and acc > base
    if not g["use"]:
        g["why"] = "didn’t beat today’s guess on your photos" if n >= 5 else "fewer than 5 photos"
    return g


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")

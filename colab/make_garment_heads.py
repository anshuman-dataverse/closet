"""Writes garment_heads.ipynb (run: python3 colab/make_garment_heads.py). Edit cells here."""

from __future__ import annotations

import json
from pathlib import Path

CELLS: list[tuple[str, str]] = []


def md(s: str) -> None:
    CELLS.append(("markdown", s.strip()))


def code(s: str) -> None:
    CELLS.append(("code", s.strip()))


md("""
# Garment heads: category, type, pattern, sleeve and fit (Closet)

Trains small classifiers on the **same FashionCLIP embedding your Mac already computes** for
each piece, so nothing new runs on the Mac. Personal, non-commercial use.

**Data**
- [Fashionpedia](https://github.com/cvdfoundation/fashionpedia) (Jia et al., ECCV 2020):
  45,623 training photos with per-garment masks and attributes (silhouette, length, pattern…).
  Annotations CC BY 4.0; photos carry their own licenses, many non-commercial.
- [Clothing dataset](https://github.com/alexeygrigorev/clothing-dataset) (Grigorev et al.), CC0:
  5,403 phone photos of real clothes.
- DeepFashion (optional, last section): only prints its attribute files until we've read them.

**The test that counts is your photos.** Upload `closet-eval.zip` from
`cd worker && uv run closet-worker export-eval` (your labeled photos plus Closet's code). A head
is switched on only where it beats what your Mac does today on those photos. Everything else
stays as it is, and the report says why.

**Runtime:** GPU (T4). Downloading and cutting out ~170,000 garments takes most of the time
(about 1 hour). Embeddings are saved to Drive, so a rerun skips that part.
""")

code("""
USE_CC0 = True
MAX_FP_IMAGES = 0          # 0 = all 45,623 Fashionpedia training photos; e.g. 3000 for a quick test
COMMERCIAL_ONLY = False    # personal use: all Fashionpedia photos
DRIVE_OUT = "/content/drive/MyDrive/closet/heads"
DEEPFASHION_DIR = "/content/drive/MyDrive/DeepFashion"   # optional: a shortcut to the official folder
SEED = 42
""")

md("## 1. Setup")
code("""
import os, sys, json, subprocess, pathlib, random, zipfile, hashlib
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pycocotools", "safetensors",
                "open_clip_torch", "rembg[gpu]", "scikit-image", "scikit-learn", "pyyaml"], check=True)
import numpy as np, torch
assert torch.cuda.is_available(), "Runtime → Change runtime type → GPU"
random.seed(SEED); np.random.seed(SEED)
from google.colab import drive, files
drive.mount("/content/drive")
OUT = pathlib.Path(DRIVE_OUT); OUT.mkdir(parents=True, exist_ok=True)
print(torch.cuda.get_device_name(0))
""")

md("""
## 2. Your labeled photos and Closet's code
Upload `closet-eval.zip` (from `closet-worker export-eval`, run after this update so it includes
the training code). Fill the `category`, `type`, `pattern` and `fit` columns in `labels.csv` first:
blank cells are simply not tested.
""")
code("""
import re, shutil
up = files.upload()
name = next(iter(up))
root = pathlib.Path("/content/eval"); shutil.rmtree(root, ignore_errors=True)
with zipfile.ZipFile(name) as z:
    z.extractall(root)
sys.path.insert(0, str(root / "code"))
need = ["code/train/garment_heads.py", "code/closet_worker/vision/heads.py"]
missing = [n for n in need if not (root / n).exists()]
assert not missing, f"Old export: rerun closet-worker export-eval after updating. Missing {missing}"
from train import garment_heads as T
from closet_worker.vision import heads as H
from closet_worker.vision.embed import load_embedder, FASHION_CLIP
from closet_worker.bundle import write_bundle
print(sum(1 for _ in open(root / "labels.csv")) - 1, "labeled rows")
""")

md("## 3. Fashionpedia (official download, ~4 GB)")
code("""
FP = pathlib.Path("/content/fp"); FP.mkdir(exist_ok=True)
base = "https://s3.amazonaws.com/ifashionist-dataset"
for rel in ["annotations/instances_attributes_train2020.json", "annotations/instances_attributes_val2020.json",
            "images/train2020.zip", "images/val_test2020.zip"]:
    dst = FP / pathlib.Path(rel).name
    if not dst.exists():
        subprocess.run(["wget", "-q", "-O", str(dst), f"{base}/{rel}"], check=True)
for z in ["train2020.zip", "val_test2020.zip"]:
    marker = FP / (z + ".done")
    if not marker.exists():
        subprocess.run(["unzip", "-q", "-o", str(FP / z), "-d", str(FP)], check=True); marker.touch()
img_dirs = [p for p in FP.iterdir() if p.is_dir()]
print("image folders:", [p.name for p in img_dirs])
def fp_path(name):
    for d in img_dirs:
        if (d / name).exists():
            return d / name
    return None

ann_tr = json.load(open(FP / "instances_attributes_train2020.json"))
ann_va = json.load(open(FP / "instances_attributes_val2020.json"))
if MAX_FP_IMAGES:
    keep = {i["id"] for i in random.Random(SEED).sample(ann_tr["images"], MAX_FP_IMAGES)}
    ann_tr = {**ann_tr, "images": [i for i in ann_tr["images"] if i["id"] in keep]}
fp_train = T.fashionpedia_examples(ann_tr, COMMERCIAL_ONLY)
fp_val = T.fashionpedia_examples(ann_va, COMMERCIAL_ONLY)
from collections import Counter
def counts(ex):
    return {k: dict(Counter(e.labels[k] for e in ex if k in e.labels).most_common()) for k in
            ["category", "type", "pattern", "sleeve", "fit/tops", "fit/bottoms"]}
print(len(fp_train), "train garments,", len(fp_val), "val garments")
print(json.dumps(counts(fp_train), indent=1)[:3000])
""")

md("## 4. Clothing dataset (CC0)")
code("""
cc0_train, cc0_test = [], []
if USE_CC0:
    CC = pathlib.Path("/content/clothing-dataset")
    if not CC.exists():
        subprocess.run(["git", "clone", "-q", "--depth", "1",
                        "https://github.com/alexeygrigorev/clothing-dataset", str(CC)], check=True)
    import csv
    cc0 = T.cc0_examples(csv.DictReader(open(CC / "images.csv")))
    tr, te = T.split_by_group(cc0, 0.2, SEED)
    cc0_train, cc0_test = [cc0[i] for i in tr], [cc0[i] for i in te]
    print(len(cc0_train), "train,", len(cc0_test), "test (split by sender)")
""")

md("""
## 5. Cut out and embed (FashionCLIP, the Mac's model)
Each garment is cut out with its mask onto white, like Closet's cut-outs. Saved to Drive.
""")
code("""
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
E = load_embedder(FASHION_CLIP, "cuda")

def crop_of(e):
    p = fp_path(e.image) if e.source == "fashionpedia" else CC / "images" / e.image
    if p is None or not p.exists():
        return None
    try:
        return T.garment_crop(Image.open(p), e)
    except Exception:
        return None

def embed_all(examples, tag):
    cache = OUT / f"emb_{tag}_{len(examples)}.npz"
    if cache.exists():
        z = np.load(cache)
        return z["x"], list(z["keep"])
    xs, keep = [], []
    from tqdm.auto import tqdm
    with ThreadPoolExecutor(8) as pool:
        for s in tqdm(range(0, len(examples), 256), desc=tag):
            crops = list(pool.map(crop_of, examples[s:s + 256]))
            ok = [(s + k, c) for k, c in enumerate(crops) if c is not None]
            if ok:
                xs.append(E.image([c for _, c in ok])); keep += [k for k, _ in ok]
    x = np.concatenate(xs).astype(np.float32)
    np.savez(cache, x=x, keep=np.array(keep))
    return x, keep

sets = {"fp_train": fp_train, "fp_val": fp_val, "cc0_train": cc0_train, "cc0_test": cc0_test}
EMB = {}
for tag, ex in sets.items():
    if ex:
        x, keep = embed_all(ex, tag)
        EMB[tag] = (x, [ex[i] for i in keep])
        print(tag, x.shape, f"({len(ex) - len(keep)} skipped: too small or unreadable)")
""")

md("""
## 6. Train the heads
Logistic regression on the embeddings, class-balanced. Labels with fewer than 30 training
examples are dropped (listed in the report). Tested on Fashionpedia's own validation split and
on the CC0 test photos, which were never used for training.
""")
code("""
HEADS = ["category", "type", "pattern", "sleeve", "fit/tops", "fit/bottoms"]
def xy(tags, head):
    xs, ys = [], []
    for t in tags:
        if t in EMB:
            x, ex = EMB[t]
            idx = [i for i, e in enumerate(ex) if head in e.labels]
            if idx:
                xs.append(x[idx]); ys += [ex[i].labels[head] for i in idx]
    return (np.concatenate(xs) if xs else np.zeros((0, E.dim), np.float32)), ys

TRAINED, REPORT = {}, {}
for head in HEADS:
    xtr, ytr = xy(["fp_train", "cc0_train"], head)
    xte, yte = xy(["fp_val"], head)
    t = T.train_head(head, xtr, ytr, xte, yte)
    if t is None:
        REPORT[head] = {"skipped": "fewer than 2 labels with 30+ examples"}; print(head, "skipped"); continue
    TRAINED[head] = t
    rep = dict(t.report)
    xc, yc = xy(["cc0_test"], head)
    if len(yc):
        h = H.Head(head, tuple(t.labels), t.w, t.b, 0.0)
        pred = [h.predict(v)[0] for v in xc]
        rep["cc0_test"] = {"n": len(yc), "accuracy": round(float(np.mean([p == y for p, y in zip(pred, yc)])), 4)}
    REPORT[head] = rep
    print(f"{head:12} Fashionpedia val acc {rep['test_accuracy']} (n={rep['test_n']})",
          f" CC0 test acc {rep.get('cc0_test', {}).get('accuracy')}", " dropped:", rep["dropped_too_few"])
""")

md("""
## 7. Your photos decide
For each labeled photo: today's guess (zero-shot, exactly as the Mac does it) against the head.
""")
code("""
from eval.tagging import read_labels, norm, norm_fit, CATEGORY_BY_NORM
from closet_worker.vision.cutout import Cutter
from closet_worker.vision.tagger import TextBank, tag
from closet_worker.vision.color import Palette
from closet_worker.vision.fit import guess_fit, load_fits
from closet_worker.vocab import load_vocab
rows = read_labels(root / "labels.csv")
meta = json.loads((root / "meta.json").read_text()) if (root / "meta.json").exists() else {}
vocab = load_vocab(); bank = TextBank(E, vocab); pal = Palette.from_dict(vocab.colors); cutter = Cutter()
fv = load_fits()
live = {h: H.Head(h, tuple(t.labels), t.w, t.b, 0.5) for h, t in TRAINED.items()}
cmp = {h: ([], [], []) for h in HEADS}   # head preds, today's preds, truth
for r in rows:
    c = cutter.cut(Image.open(root / "photos" / r.file).convert("RGB"))
    s, vec = tag(c.crop, c.rgb, c.mask, E, bank, pal)
    cat = CATEGORY_BY_NORM.get(r.truth["category"]) or s.category
    def add(head, truth, today):
        if truth and head in live:
            label, p = live[head].predict(vec)
            cmp[head][0].append(label if p >= live[head].min_p else None)
            cmp[head][1].append(today); cmp[head][2].append(truth)
    add("category", CATEGORY_BY_NORM.get(r.truth["category"]), s.category)
    add("type", r.truth["type"], norm(s.type))
    add("pattern", r.truth["pattern"], norm(s.pattern))
    g = fv.group_for(cat)
    if r.truth["fit"] and g is not None and g.name in ("tops", "bottoms"):
        fg = guess_fit(vec, c.mask, cat, r.truth["type"] or s.type, meta.get("wears"), E)
        add(f"fit/{g.name}", r.truth["fit"], fg.fit if fg else None)
GATE = {}
for h, (ours, today, truth) in cmp.items():
    if h in live:
        GATE[h] = T.gate_against_baseline(ours, today, truth, h.startswith("fit/"))
        g = GATE[h]
        print(f"{h:12} your photos n={g['n']:3}  head {g.get('accuracy')}  today {g.get('baseline_accuracy')}  ->",
              "ON" if g["use"] else f"off ({g.get('why')})")
print("sleeve: no sleeve column in labels.csv yet, so it stays off on the Mac (measured above on public data only)")
""")

md("## 8. Save and download (one zip for `closet-worker import`)")
code("""
import datetime
heads = [H.Head(h, tuple(t.labels), t.w, t.b, 0.5) for h, t in TRAINED.items()]
extra = {"gate": GATE, "report": REPORT, "commercial_only": COMMERCIAL_ONLY,
         "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "sources": {"fashionpedia": "Jia et al., ECCV 2020; annotations CC BY 4.0; photo licenses vary (many non-commercial)",
                     "clothing-dataset": "Grigorev et al., CC0 1.0" if USE_CC0 else None}}
H.save(OUT, E.model_id, heads, extra)
card = ["# Closet garment heads", "", f"Embedder: {E.model_id}. Personal, non-commercial use.", "",
        "## Public test sets", "```", json.dumps(REPORT, indent=1)[:20000], "```", "",
        "## Your photos (the gate)", "```", json.dumps(GATE, indent=1), "```", "",
        "A head is used on the Mac only where it beat today’s guess on your photos; fit heads per",
        "fit, right ≥70% over ≥5 suggestions. Sleeve length has no label column yet, so it stays off.",
        "Fashionpedia photos show clothes being worn; Closet mostly sees flat-lays, which is why your",
        "photos are the test that decides."]
(OUT / "MODEL_CARD.md").write_text("\\n".join(card) + "\\n")
zp = write_bundle("heads", {n: OUT / n for n in ["heads.safetensors", "heads.json", "MODEL_CARD.md"]},
                  OUT / f"closet-heads-{datetime.date.today().isoformat()}.zip")
print("wrote", zp, f"{zp.stat().st_size / 1e6:.1f} MB")
files.download(str(zp))
""")

md("""
## 9. DeepFashion (optional: read its files first)
DeepFashion's Category and Attribute benchmark (289,222 photos, non-commercial research use) is
on Google Drive. Open the folder linked from
[its page](https://mmlab.ie.cuhk.edu.hk/projects/DeepFashion/AttributePrediction.html), choose
**Add shortcut to Drive**, name it `DeepFashion`, then run this cell. It only lists the files and
prints the attribute names, so the mapping to Closet's labels can be written from what's really
there, not from memory.
""")
code("""
DF = pathlib.Path(DEEPFASHION_DIR)
if not DF.exists():
    print("No DeepFashion shortcut at", DF)
else:
    listing = sorted(str(p.relative_to(DF)) for p in DF.rglob("*") if p.is_file() and p.suffix in (".txt", ".zip", ".json"))
    print("\\n".join(listing[:60]))
    for p in DF.rglob("*.txt"):
        if any(k in p.name for k in ("attr_cloth", "category_cloth", "attr_type", "fine")) and "img" not in p.name:
            print("\\n====", p.relative_to(DF)); print("".join(open(p, errors="replace").readlines()[:80]))
    (OUT / "deepfashion_listing.txt").write_text("\\n".join(listing))
""")


def notebook() -> dict[str, object]:
    cells = []
    for kind, src in CELLS:
        lines = [line + "\n" for line in src.split("\n")]
        lines[-1] = lines[-1].rstrip("\n")
        c: dict[str, object] = {"cell_type": kind, "metadata": {}, "source": lines}
        if kind == "code":
            c.update(execution_count=None, outputs=[])
        cells.append(c)
    return {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"provenance": [], "gpuType": "T4"},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 0,
    }


if __name__ == "__main__":
    out = Path(__file__).with_name("garment_heads.ipynb")
    out.write_text(json.dumps(notebook(), indent=1, ensure_ascii=False) + "\n")
    print("wrote", out)

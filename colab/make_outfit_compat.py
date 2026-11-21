"""Writes outfit_compat.ipynb (run: python3 colab/make_outfit_compat.py). Edit cells here, not in
the notebook, so the notebook stays reviewable as code."""

from __future__ import annotations

import json
from pathlib import Path

CELLS: list[tuple[str, str]] = []


def md(s: str) -> None:
    CELLS.append(("markdown", s.strip()))


def code(s: str) -> None:
    CELLS.append(("code", s.strip()))


md("""
# Outfit compatibility model: measure, then export (SPEC 5.11)

This notebook checks whether a public outfit model (OutfitTransformer with FashionCLIP, from
[owj0421/outfit-transformer](https://github.com/owj0421/outfit-transformer) @ `eef4be55`, MIT)
really works before Closet uses it. It reports what it measures, nothing copied from a README.

**What it does**
1. Loads the author's checkpoint **safely** (`weights_only=True`) and keeps only the small
   scoring head.
2. Embeds Polyvore items with **the same embedder code the Mac runs** (`embed.py`), after a
   parity check against the author's encoder.
3. Measures compatibility AUC and fill-in-the-blank accuracy on the Polyvore test splits,
   plus two "closer to Closet" variants (short text; cut-out photos).
4. Exports `compat_head.safetensors`, `compat_config.json` and `MODEL_CARD.md` to Drive.

**Data:** only the public Polyvore Outfits dataset (research use). No style photos and no keys
are used here. Whether the model helps *you* is measured on the Mac by
`closet-worker compat-eval`, from your own logged outfits.

**Runtime:** GPU (T4 is enough). With `QUICK = 0` (full test sets) expect about 1–2 hours,
mostly embedding images. Start with `QUICK = 500` to check that everything runs.
""")

code("""
QUICK = 500          # outfits per test set; 0 = the full test sets (the numbers to report)
DRIVE_OUT = "/content/drive/MyDrive/closet/compat"
REPO_COMMIT = "eef4be55dbdc2f86f47e3a5d9d4b85c2f17de08b"
CKPT_GDRIVE_ID = "1mzNqGBmd8UjVJjKwVa5GdGYHKutZKSSi"   # from the repo's readme
README_AUC, README_FITB = 0.95, 69.24                  # what the repo reports (CLIP variant)
SEED = 42
""")

md("## 1. Setup")
code("""
import os, sys, json, hashlib, random, pathlib, subprocess
os.environ["WANDB_MODE"] = "disabled"
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gdown", "datasets", "safetensors"], check=True)

import numpy as np, torch
from packaging.version import Version
assert torch.cuda.is_available(), "Runtime → Change runtime type → GPU"
assert Version(torch.__version__.split("+")[0]) >= Version("2.6"), "need torch ≥ 2.6 (safe loading)"
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
DEV = "cuda"
print(torch.__version__, torch.cuda.get_device_name(0))
""")

md("""
## 2. Closet's own code
Upload two files from your repo, unchanged:
`worker/closet_worker/recsys/compat_head.py` and `worker/closet_worker/vision/embed.py`.
(Or put them in `MyDrive/closet/code/` and this cell picks them up.)
""")
code("""
from google.colab import drive, files
drive.mount("/content/drive")
code_dir = pathlib.Path("/content/closet_code"); code_dir.mkdir(exist_ok=True)
need = ["compat_head.py", "embed.py"]
src = pathlib.Path("/content/drive/MyDrive/closet/code")
for n in need:
    if (src / n).exists():
        (code_dir / n).write_bytes((src / n).read_bytes())
if not all((code_dir / n).exists() for n in need):
    for n, data in files.upload().items():
        (code_dir / n).write_bytes(data)
assert all((code_dir / n).exists() for n in need), f"upload {need}"
# A saved copy (Drive or an earlier upload) can be out of date: check, and ask again if so.
def current(n):
    t = (code_dir / n).read_text()
    return "max_length" in t if n == "embed.py" else "def head_state" in t
for n in need:
    if not current(n):
        print(f"{n} is out of date (from Drive or an earlier upload). Upload the new one.")
        for got, data in files.upload().items():
            (code_dir / n).write_bytes(data)
        if (src / n).exists():
            (src / n).write_bytes((code_dir / n).read_bytes())  # refresh the Drive copy too
    assert current(n), f"{n} is still out of date"
sys.path.insert(0, str(code_dir))
import compat_head, embed
print({n: hashlib.sha256((code_dir / n).read_bytes()).hexdigest()[:12] for n in need})
""")

md("""
## 3. The author's checkpoint, loaded safely
The `.pth` file is a pickle. `weights_only=True` refuses anything but tensors and plain data. If
it refuses, **stop**: don't switch to unsafe loading.
""")
code("""
ck_dir = pathlib.Path("/content/ot_ckpt")
if not ck_dir.exists():
    subprocess.run(["gdown", "--id", CKPT_GDRIVE_ID, "-O", "/content/ckpt.zip"], check=True)
    subprocess.run(["unzip", "-q", "/content/ckpt.zip", "-d", str(ck_dir)], check=True)
cands = sorted(p for p in ck_dir.rglob("*") if p.suffix in (".pth", ".pt"))
for p in cands:
    print(p.relative_to(ck_dir), f"{p.stat().st_size/1e6:.0f} MB")
""")
code("""
# Pick the compatibility (CP) checkpoint of the CLIP model. Set CKPT by hand if this guesses wrong.
cp = [p for p in cands if "compat" in str(p).lower() or "cp" in p.parent.name.lower()]
CKPT = (cp or cands)[0]
print("using", CKPT)
ck = torch.load(CKPT, map_location="cpu", weights_only=True)
cfg = ck.get("config", {})
print(json.dumps(cfg, indent=1))
assert cfg.get("item_enc_clip_model_name") == "patrickjohncyh/fashion-clip", "not the FashionCLIP variant"
assert cfg.get("aggregation_method", "concat") == "concat"
HEAD_CFG = dict(
    n_head=cfg.get("transformer_n_head", 16), d_ffn=cfg.get("transformer_d_ffn", 2024),
    n_layers=cfg.get("transformer_n_layers", 6), dropout=cfg.get("transformer_dropout", 0.3),
)
head = compat_head.build(**HEAD_CFG)
state = compat_head.head_state(ck["model"])
head.load_state_dict(state, strict=True)      # fails loudly on any missing or extra key
head = head.to(DEV).eval()
print("head parameters:", sum(p.numel() for p in head.parameters()) / 1e6, "M")
""")

md("## 4. Polyvore data (Hugging Face, public)")
code("""
from datasets import load_dataset
items = load_dataset("owj0421/polyvore", split="data")            # ~2.2 GB, images included
row_of = {iid: i for i, iid in enumerate(items["item_id"])}

def outfits(kind, task):
    # Negative outfits borrow items from other splits, so map ids across all of them.
    conv = {}
    for split in ("train", "validation", "test"):
        sets = load_dataset("owj0421/polyvore-outfits", f"{kind}_default", split=split)
        conv.update({f"{s['set_id']}_{it['index']}": it["item_id"] for s in sets for it in s["items"]})
    data = load_dataset("owj0421/polyvore-outfits", f"{kind}_{task}", split="test")
    if QUICK:
        data = data.shuffle(seed=SEED).select(range(min(QUICK, len(data))))
    return data, conv

# Every negative compatibility outfit in this copy has one empty item id ("") and no positive
# does: left in, the label would leak. Drop empty ids and count them.
EMPTY_IDS = 0
def real(ids):
    global EMPTY_IDS
    ids = list(ids)
    keep = [x for x in ids if x]
    EMPTY_IDS += len(ids) - len(keep)
    return keep

TESTS = {k: {t: outfits(k, t) for t in ("compatibility", "fill_in_the_blank")} for k in ("nondisjoint", "disjoint")}
needed = set()
for k in TESTS.values():
    for data, conv in k.values():
        for r in data:
            needed.update(conv[x] for x in real(r["items"]))
            needed.update(conv[x] for x in real(r.get("candidates") or []))
print(len(needed), "items to embed;", EMPTY_IDS, "empty item ids dropped")
DATA_NOTES = {"empty_item_ids_dropped": EMPTY_IDS}
""")

md("""
## 5. Parity: the Mac's embedder vs the author's encoder
Both must give the same vectors (cosine ≥ 0.999), or the head would get different inputs on the
Mac than it was trained on.
""")
code("""
from transformers import CLIPVisionModelWithProjection, CLIPTextModelWithProjection, CLIPImageProcessor, CLIPTokenizer
E = embed.HfClipEmbedder(embed.FASHION_CLIP, device=DEV)
M = "patrickjohncyh/fashion-clip"
v_ref = CLIPVisionModelWithProjection.from_pretrained(M).to(DEV).eval()
t_ref = CLIPTextModelWithProjection.from_pretrained(M).to(DEV).eval()
proc = CLIPImageProcessor.from_pretrained(M, do_convert_rgb=False)
tok = CLIPTokenizer.from_pretrained(M)

def ref_image(imgs):
    with torch.no_grad():
        x = proc(images=imgs, return_tensors="pt").to(DEV)
        return torch.nn.functional.normalize(v_ref(**x).image_embeds, dim=-1).cpu().numpy()

def ref_text(texts):
    with torch.no_grad():
        x = tok(texts, max_length=64, padding="max_length", truncation=True, return_tensors="pt").to(DEV)
        return torch.nn.functional.normalize(t_ref(**x).text_embeds, dim=-1).cpu().numpy()

sample = random.sample(sorted(needed), 50)
rows = [items[row_of[i]] for i in sample]
imgs = [r["image"].convert("RGB") for r in rows]
txts = [r["url_name"] or "" for r in rows]
cos_i = (E.image(imgs) * ref_image(imgs)).sum(1)
cos_t = (E.text(txts, max_length=64) * ref_text(txts)).sum(1)  # the author's encoder cuts at 64
PARITY = {"image_min_cos": float(cos_i.min()), "text_min_cos": float(cos_t.min())}
print(PARITY)
assert cos_i.min() >= 0.999 and cos_t.min() >= 0.999, "embeddings differ: stop and investigate"
""")

md("""
## 6. Embed the test items (as trained, and two variants closer to Closet)
- `trained`: product photo + the item's Polyvore name, as the model was trained.
- `short_text`: the text is only the Polyvore category (Closet's text is short, like "navy chinos").
- `cutout`: the photo goes through rembg on a plain background, like Closet's cutouts (a subset).
""")
code("""
from tqdm.auto import tqdm
ids = sorted(needed)
IMG, TXT, CAT = {}, {}, {}
B = 128
for s in tqdm(range(0, len(ids), B)):
    chunk = ids[s:s + B]
    rs = [items[row_of[i]] for i in chunk]
    iv = E.image([r["image"].convert("RGB") for r in rs])
    tv = E.text([r["url_name"] or "" for r in rs], max_length=64)  # as in training
    cv = E.text([r["category"] or "" for r in rs])
    for i, a, b, c in zip(chunk, iv, tv, cv):
        IMG[i], TXT[i], CAT[i] = a, b, c
""")

md("## 7. Metrics")
code("""
from sklearn.metrics import roc_auc_score

def score_sets(sets, img, txt, bs=512):
    out = []
    for s in range(0, len(sets), bs):
        chunk = sets[s:s + bs]
        n = max(len(o) for o in chunk)
        x = np.zeros((len(chunk), n, 1024), dtype=np.float32)
        for j, o in enumerate(chunk):
            for k, i in enumerate(o[:16]):
                x[j, k] = np.concatenate([img[i], txt[i]])
        lengths = torch.tensor([min(len(o), 16) for o in chunk])
        with torch.no_grad():
            out.append(head(torch.from_numpy(x).to(DEV), lengths).float().cpu().numpy())
    return np.concatenate(out)

def cp_auc(kind, img, txt):
    data, conv = TESTS[kind]["compatibility"]
    sets = [[conv[x] for x in real(r["items"])] for r in data]
    return float(roc_auc_score([int(r["label"]) for r in data], score_sets(sets, img, txt)))

def fitb_acc(kind, img, txt):
    # FITB by compatibility: the candidate that makes the most compatible outfit wins.
    # (The repo's 69.24 uses a separately trained retrieval model, so this is not the same number.)
    # The stored answer is often candidate 0, so shuffle (seeded) to keep ties from scoring.
    data, conv = TESTS[kind]["fill_in_the_blank"]
    rng = random.Random(SEED)
    sets, labels = [], []
    for r in data:
        base = [conv[x] for x in real(r["items"])]
        order = list(range(len(r["candidates"])))
        rng.shuffle(order)
        sets += [base + [conv[r["candidates"][j]]] for j in order]
        labels.append(order.index(int(r["label"])))
    p = score_sets(sets, img, txt).reshape(len(labels), -1)
    return float((p.argmax(1) == np.array(labels)).mean() * 100)

RESULTS = {}
for kind in ("nondisjoint", "disjoint"):
    for name, txt in (("trained", TXT), ("short_text", CAT)):
        RESULTS[f"{kind}/{name}"] = {"cp_auc": round(cp_auc(kind, IMG, txt), 4),
                                     "fitb_by_cp_pct": round(fitb_acc(kind, IMG, txt), 2)}
        print(kind, name, RESULTS[f"{kind}/{name}"])
""")

md("### Cut-out photos (rembg, like Closet), on up to 300 compatibility outfits")
code("""
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "rembg[gpu]"], check=True)
from rembg import new_session, remove
from PIL import Image
sess = new_session("isnet-general-use")
data, conv = TESTS["nondisjoint"]["compatibility"]
sub = data.select(range(min(300, len(data))))
sub_ids = sorted({conv[x] for r in sub for x in real(r["items"])})
CUT = {}
for s in tqdm(range(0, len(sub_ids), 32)):
    chunk = sub_ids[s:s + 32]
    ims = []
    for i in chunk:
        cut = remove(items[row_of[i]]["image"].convert("RGB"), session=sess)
        bg = Image.new("RGB", cut.size, (255, 255, 255)); bg.paste(cut, mask=cut.split()[-1])
        ims.append(bg)
    for i, v in zip(chunk, E.image(ims)):
        CUT[i] = v
sets = [[conv[x] for x in real(r["items"])] for r in sub]
labels = [int(r["label"]) for r in sub]
RESULTS["nondisjoint/cutout_subset"] = {
    "n_outfits": len(sub),
    "cp_auc_product_photos": round(float(roc_auc_score(labels, score_sets(sets, IMG, TXT))), 4),
    "cp_auc_cutouts": round(float(roc_auc_score(labels, score_sets(sets, CUT, TXT))), 4),
}
print(RESULTS["nondisjoint/cutout_subset"])
""")

md("""
## 8. Verdict
If the measured AUC on the full test sets (`QUICK = 0`) is more than 2 points under the
README's, don't export: report the numbers. Training our own head is a separate step.
""")
code("""
auc = RESULTS["nondisjoint/trained"]["cp_auc"]
print(f"measured CP AUC {auc:.3f} vs README {README_AUC}; QUICK={QUICK}")
OK_TO_EXPORT = QUICK == 0 and auc >= README_AUC - 0.02
print("OK to export" if OK_TO_EXPORT else "Not exporting: run with QUICK = 0, or the model underperforms.")
""")

md("## 9. Export to Drive (only the head, as safetensors)")
code("""
assert OK_TO_EXPORT, "see the verdict above"
from safetensors.torch import save_file
out = pathlib.Path(DRIVE_OUT); out.mkdir(parents=True, exist_ok=True)
wf = out / "compat_head.safetensors"
save_file({k: v.detach().cpu().contiguous() for k, v in head.state_dict().items()}, str(wf))
sha = hashlib.sha256(wf.read_bytes()).hexdigest()
config = {**HEAD_CFG, "max_items": 16, "text_template": "{color} {type}",
          "embedder": "patrickjohncyh/fashion-clip", "repo_commit": REPO_COMMIT, "sha256": sha}
(out / "compat_config.json").write_text(json.dumps(config, indent=2) + "\\n")

scope = "full" if QUICK == 0 else f"{QUICK} per set"
card = f\"\"\"# Outfit compatibility head (Closet)

Source: owj0421/outfit-transformer @ {REPO_COMMIT} (MIT), CLIP variant, checkpoint `{CKPT.name}`.
Only the scoring head is exported (style_enc, predict_ffn, task/predict/pad embeddings).
Inputs: FashionCLIP image (512) + FashionCLIP text (512) per item.

## Measured here (Polyvore Outfits test, {scope})
```
{json.dumps(RESULTS, indent=2)}
```
Embedding parity with Closet's embedder: {json.dumps(PARITY)}
Data notes: {json.dumps(DATA_NOTES)} (negatives in this copy carry one empty id; dropped so the
label can't leak through it).

README claims CP AUC {README_AUC}, FITB {README_FITB} (FITB there uses a retrieval model; ours is
FITB by compatibility scoring, so it isn't the same number).

## Limits
- Trained on Polyvore (product photos, mostly womenswear, 2010s web fashion).
- Closet's text is short ("navy chinos"); see `short_text`. Closet's photos are cut-outs; see
  `cutout_subset`.
- It says nothing about your colors or body. Closet uses it only if it beats the rules on your
  own logged outfits (`closet-worker compat-eval`).
- Polyvore Outfits is for research use. Fine for a personal project; don't redistribute.

SHA-256 of compat_head.safetensors: {sha}
\"\"\"
(out / "MODEL_CARD.md").write_text(card)
print("wrote", sorted(p.name for p in out.iterdir()), sha)
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
    out = Path(__file__).with_name("outfit_compat.ipynb")
    out.write_text(json.dumps(notebook(), indent=1, ensure_ascii=False) + "\n")
    print("wrote", out)

# Colab notebooks

Training and evaluation only. Live inference always runs on the Mac worker.

| Notebook | Phase | What it does |
|---|---|---|
| `tagging_eval.ipynb` | 2 (ready) | FashionCLIP vs Marqo-FashionSigLIP on your ~50 hand-checked photos; picks `EMBED_MODEL` |
| `train_ranker.ipynb` | 6 | Trains the personal ranker from `suggestion_events` and embeddings; same guardrail as the Mac (must beat rules-only) |
| `outfit_compat.ipynb` | 5.11 (ready) | Measures the public OutfitTransformer (FashionCLIP) on Polyvore, checks it against Closet’s embedder, exports only its scoring head |

Data flow: the Mac exports a dataset file, which you upload to Colab (or Google Drive).
Training notebooks save a versioned artifact, and an import command on the Mac (built in Phase 6)
records it in `model_versions`. The Supabase service-role key never goes into Colab.

## Running the tagging eval

1. On the Mac, run `cd worker && uv run closet-worker export-eval`. It writes `~/ClosetPhotos/eval/` with `labels.csv`, prefilled from the app.
2. Fix the wrong rows in `labels.csv`, then run the export again. Your edits are kept; only the zip is rebuilt.
3. Open `colab/tagging_eval.ipynb` in Colab: File → Upload notebook, or open it from GitHub. Choose a T4 GPU, upload `closet-eval.zip`, and run all cells.
4. Set `EMBED_MODEL` in `worker/.env` to the recommended model.

The same eval runs locally too: `uv run python -m eval.tagging --data ~/ClosetPhotos/eval`.

## Running the outfit model check (`outfit_compat.ipynb`)

The notebook is generated from `colab/make_outfit_compat.py`. Edit that file, then run
`python3 colab/make_outfit_compat.py`.

1. Put `worker/closet_worker/recsys/compat_head.py` and `worker/closet_worker/vision/embed.py`
   in `MyDrive/closet/code/` (or upload them when the notebook asks).
2. Open `colab/outfit_compat.ipynb` in Colab with a T4 GPU. Run all cells once with `QUICK = 500`
   to check that everything works, then set `QUICK = 0` and run again for the real numbers (1–2 hours).
3. If the verdict says OK, it writes `compat_head.safetensors`, `compat_config.json` and
   `MODEL_CARD.md` to `MyDrive/closet/compat/`. Copy them to `~/.cache/closet/compat/` on the Mac.
4. On the Mac, run `cd worker && uv run closet-worker compat-eval`. It replays your logged outfits
   and turns the model on only if it beats rules alone on at least 30 of them. Rerun it as you log more.

Safety: the author’s `.pth` checkpoint is a pickle, so it’s opened only in Colab, with
`weights_only=True`. The Mac loads only the safetensors head, after a SHA-256 check.

# Colab notebooks

Training and evaluation only. Live inference always runs on the Mac worker.

| Notebook | Phase | What it does |
|---|---|---|
| `tagging_eval.ipynb` | 2 (ready) | FashionCLIP vs Marqo-FashionSigLIP on your ~50 hand-checked photos; picks `EMBED_MODEL` |
| `train_ranker.ipynb` | 6 | Trains the personal ranker from `suggestion_events` and embeddings; same guardrail as the Mac (must beat rules-only) |
| `polyvore_compat.ipynb` | 6 (optional) | Embeds a Polyvore Outfits subset and trains a compatibility head |

Data flow: the Mac exports a dataset file, which you upload to Colab (or Google Drive).
Training notebooks save a versioned artifact, and an import command on the Mac (built in Phase 6)
records it in `model_versions`. The Supabase service-role key never goes into Colab.

## Running the tagging eval

1. On the Mac, run `cd worker && uv run closet-worker export-eval`. It writes `~/ClosetPhotos/eval/` with `labels.csv`, prefilled from the app.
2. Fix the wrong rows in `labels.csv`, then run the export again. Your edits are kept; only the zip is rebuilt.
3. Open `colab/tagging_eval.ipynb` in Colab: File → Upload notebook, or open it from GitHub. Choose a T4 GPU, upload `closet-eval.zip`, and run all cells.
4. Set `EMBED_MODEL` in `worker/.env` to the recommended model.

The same eval runs locally too: `uv run python -m eval.tagging --data ~/ClosetPhotos/eval`.

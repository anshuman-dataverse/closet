# Colab notebooks

Training and evaluation only. Live inference always runs on the Mac worker.

| Notebook | Phase | What it does |
|---|---|---|
| `tagging_eval.ipynb` | 2 | FashionCLIP vs Marqo-FashionSigLIP on your 50 hand-labeled photos; picks `EMBED_MODEL` |
| `train_ranker.ipynb` | 6 | Trains the personal ranker from `suggestion_events` and embeddings; same guardrail as the Mac (must beat rules-only) |
| `polyvore_compat.ipynb` | 6 (optional) | Embeds a Polyvore Outfits subset and trains a compatibility head |

Data flow: the Mac exports a dataset file, which you upload to Colab (or Google Drive).
The notebook trains and saves a versioned artifact, and an import command on the Mac (built in Phase 6)
records it in `model_versions`. The Supabase service-role key never goes into Colab.

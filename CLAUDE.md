# Closet: working notes

The spec is **SPEC.md** (read it before planning). The look, copy and interactions are in `design-reference/closet-demo.html`.
Work phase by phase (SPEC 12). Plan each phase and get an OK first. Ask before adding paid services or deps that need accounts.
Done: Phases 0–1, 3–5 (free hunts, price watch, backups; GPT hunts not built, the owner chose free only). Phase 2 (vision) counts as done once the Colab eval meets ≥90% category / ≥70% type. Next: Phase 6.
Phase 7 wishlist, added by the owner: virtual try-on on the Mac (free, slow). Vercel has no GPUs.

## Run
- Local Supabase: `supabase start` (repo root; ports 554xx because another project uses 543xx). Studio :55423, Mailpit :55424.
- Web: `cd web && pnpm dev`. Run `pnpm dev:user` once to create ALLOWED_EMAIL locally; `pnpm seed [--reset]` loads the sample closet.
  Sign-in mail goes to Mailpit.
- Worker: `cd worker && uv run closet-worker [--fake] [--once]`. Reads `worker/.env`. launchd: `worker/launchd/install.sh`.
- SearXNG: `docker compose -f infra/searxng/docker-compose.yml up -d` → http://127.0.0.1:8888.

## Test, lint, migrate, deploy
- Web: `pnpm check` (tsc, eslint, prettier, vitest) and `pnpm e2e` (Playwright, phone 390×844 + desktop 1280).
  e2e needs local Supabase. It builds, serves on :3100, and spawns the real worker with `--fake`.
- Worker: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`.
  Integration tests skip when local Supabase is down.
- DB: add `supabase/migrations/<timestamp>_<name>.sql`, run `supabase db reset` locally, then `supabase test db`,
  then `pnpm db:types` in web/. Prod: `supabase db push`.
- Deploy: Vercel with root dir `web/` and 3 public env vars. Never put the service-role key in Vercel.

## Conventions
- Money is integer cents (USD). Worn and bought days are `date` in the profile's time zone. All other times are timestamptz.
- Every table has `user_id ... default auth.uid()` and the `owner_all` RLS policy. `jobs` and `workers` are owner read-only,
  except that the owner may insert queued jobs and delete queued ones. Views use `security_invoker`.
- `claim_job` / `requeue_stale_jobs` are service-role only. The worker filters every query by OWNER_USER_ID.
- Job kinds are listed in 3 places that must match: the `jobs.kind` check, `worker/closet_worker/jobs/__init__.py` REGISTRY,
  and `web/lib/jobs.ts` JobKind. `ping` is extra (the round-trip test). Also `KIND_LABEL` in WorkerStatus.tsx.
- `wishlist_items.check` from the spec is named `check_result` (CHECK is reserved).
- Next 16 with `cacheComponents`. Read `web/node_modules/next/dist/docs/` before using Next APIs. Middleware is `proxy.ts`.
  Don't call `Date.now()` or `new Date()` during render (it breaks the prerender). Use effects, `useSyncExternalStore`, or event handlers.
- Redirects: route handlers use `relativeRedirect`. The proxy uses `sameHostUrl` (Next normalizes the host).
- Client data goes through `lib/supabase/client.ts` with RLS. Server-only code imports `server-only`.
- Styling: tokens and classes in `web/app/globals.css`, ported from the prototype. No new card kits or gradients.
- Copy: sentence case, typographic apostrophes (’), no “Claude”/AI sparkle words, no arrows in buttons. Errors say what to do.
- Never `dangerouslySetInnerHTML`. Outside links use `target="_blank" rel="noopener noreferrer"`.
- Python: ruff (line 100), mypy strict, idempotent handlers, `TransientError` for retryable failures.
- Secrets: `worker/.env`, `infra/searxng/.env` and `web/.env.local` are gitignored (committed keys are local demo keys).

## Web data layer
- `lib/closet/store.ts` is one client store (useSyncExternalStore). It loads everything once and refetches when the tab
  becomes visible. Writes go through it so local state stays in sync. `useDerived` gives `today` (profile time zone), `byId`, `stats`.
- Atomic writes are RPCs: `log_wear` (the duplicate guard returns 'already'), `save_outfit` (replaces pieces and orders
  by category), `delete_all_my_data` (the client deletes Storage files first).
- The rules are pure functions in `lib/domain/*` (dates, money, wear, rotation, outfit, spend, colors), each with tests.
- Photos: `lib/photos.ts` (1600px + 480px JPEG, EXIF stripped, upload as soon as picked). `lib/signed-urls.ts` batches signed URLs.
- Sheets are addressed by query params (`?item=`, `?add=1`, `?outfit=`, `?edit=`, `?new=1`) through `useSheetParam`.
- e2e: `tests/e2e/data.ts` resets and seeds the owner. Bulk inserts need every key, or missing ones become null.

## Vision (worker)
- `tag_item` (`jobs/tag_item.py`): rembg `isnet-general-use` → cutout `{photo}_cutout.webp` → fashion CLIP embedding
  (`item_embeddings`, 512-d for FashionCLIP) → zero-shot type and pattern → k-means/ΔE2000 color → `items.suggestions`.
- Vocab lives in `closet_worker/vocab/*.yaml`. The clothing check compares clothing prompts with concrete non-clothing scenes,
  because CLIP can't handle "not clothing". This departs on purpose from SPEC 5.1.
- Tests use `tests/stubs.py` (no downloads). Real models run with `uv run pytest -m models`.
  Linux uses CPU-only torch (`[tool.uv.sources]`).
- Web flow: picking a photo in Add clothes saves a draft row ("New piece"), queues `tag_item`, and waits 20 s. The draft is
  deleted on cancel. Suggestions fill only untouched fields (`lib/domain/suggestions.ts`). Saved pieces show `SuggestionBox`.
- Keep sheets at a stable spot in the tree (one return with `{body}{sheet}`), or switching branches remounts them.

## Fit and labels
- Fit ids: `vocab/fits.yaml` (per category group, menswear/womenswear) → `web/lib/domain/fits.json` via
  `scripts/export-style-data.py` (CI checks it's fresh). `items.fit` is a short id; `profiles.wears` only filters choices.
- `vision/fit.py`: outline ratios (flat-lay mask) + FashionCLIP zero-shot; a guess only when they agree or the shape is silent.
  tag_item suggests a fit only if `~/.cache/closet/fit/gate.json` (from the tagging eval, same embed model) passed it.
- Labels: `read_label` job, Apple Vision OCR on the Mac (`vision/label.py`, PyObjC, darwin-only dep). Report only printed
  facts: one size, one fit word, fibers summing to 100%. Writes `suggestions.label`; the web fills empty, untouched fields.
- Colab results come back as zips with a SHA-256 manifest: `closet-worker import <zip>` (`bundle.py`). `colab/outputs/` is gitignored.
- Garment heads (`vision/heads.py`, trained by `train/garment_heads.py` in `colab/garment_heads.ipynb`): used per head only
  where they beat zero-shot on the user's labeled photos; tag_item records `suggestions.sources`.
- Backups (`jobs/backup.py`): owner-only CSV per table from one snapshot via psql `\copy` (not pg_dump: that would include
  other users), photos synced, models copied, 14 kept. `closet-worker restore` reads targets only from CLOSET_RESTORE_*.
  Fake mode runs no nightly tasks and uses `~/.closet/scheduler-fake.json`.

## Recommender (worker `recsys/`, no ML)
- `candidates.py` (structure rules), `scoring.py` (harmony, palette=0 until Phase 4, formality, weather, freshness),
  `select.py` (diversity), `engine.py`. Weights and thresholds are in `recsys/weights.yaml`. Menswear neutrals count by name.
- `suggest_outfits` logs `shown` suggestion_events; the web logs worn/saved/skipped/liked/disliked. That's Phase 6's training data.
- Unlock counts (check_wish, find_gaps) ignore wear history on purpose. Fake mode runs the real
  suggest_outfits and find_gaps; check_wish and tag_item use fixtures.
- Duplicate search: `nearest_items` RPC (pgvector, service role). Wishlist in web: `app/(app)/shop/*`, store `saveWish`/`checkWish`.
- Outfit model (SPEC 5.11): `recsys/compat_head.py` (torch-only, also run by `colab/outfit_compat.ipynb`) and `compat.py`
  (safetensors + SHA-256, `COMPAT_MODEL_DIR`). The `compat` term exists only while `gate.json` is open; `closet-worker compat-eval`
  opens it only if rules+model beat rules on ≥30 logged picks. With it closed, scores are unchanged. Never add reason text for it.

## Deal hunts and price watch (Phase 5)
- `shopping/`: `stores.py` (vocab/stores.yaml: product URL regex per store, each with a real example a test checks, plus a
  `checked` status from a live test), `fetch.py` (robots.txt honored, 1 req/s per site, 10 s, identifying UA), `parse.py`
  (extruct JSON-LD/microdata, Open Graph fallback; missing price → skipped, never estimated), `hunt.py` (queries, keep
  USD + in stock + in budget, rank, ≤2 per store, honest summary naming blocked stores; ~/.closet/store_health.json).
- Colors in hunt "why" lines only when the product's name states the color; light colors are never read from photos.
- `price_check` (09:00): a failed check is saved as "Couldn’t check: …"; the web flags drops in `lib/domain/hunts.ts`.
- As of 2026-11-22 most womenswear stores (Zara, Mango, Anthropologie, Free People) block automated reading.
- Shop a look (`shopping/look.py`, hunts.kind='look'): plan slots per occasion (PREFERRED types, palette colors, layer ≠
  top/bottom color), hunt each slot (must_have nouns, store-stated color, no pattern/kids/other gender via name, JSON-LD
  audience or breadcrumbs), assemble complete sets ≤ total budget; never show a set with a missing slot.
- SearXNG needs several engines (bing, brave, yahoo enabled in infra/searxng/settings.yml): DuckDuckGo CAPTCHAs and
  Google CSE rate-limits.
- Ideas pass a quality bar (`recsys/engine.py failed_checks`) or aren't shown; fit balance is a scoring term.
- Studio images (`vision/studio.py`, items.studio_path): clothing model (u2net_cloth_seg) ∩ edge model (isnet); a drawn
  hanger for Tops/Layers. Sample pieces: items.is_sample (Settings), excluded from Spend.
- Check my outfit: `rate_outfit` job (`recsys/rate.py`): every check with a reason, verdict in words (strong/works/rethink),
  checks without data say what would let them run. Opened from the outfit builder (Check it).

## Style profile (Phase 4)
- `analyze_profile`: MediaPipe Face and Pose (`vision/landmarks.py`; models cached in ~/.cache/closet) → `skin.py`
  (undertone, depth, contrast, lighting), `face_shape.py` (majority vote over face photos), `body.py` → `style.py`
  builds `profiles.analysis`. `{recompute:true}` reruns only the palette and text with the overrides.
- Tables: `vocab/style.yaml` (thresholds), `palettes.yaml` (36 combinations), `face_tips.yaml`.
- `tests/test_style.py` bans body and looks words in all generated text. Keep it passing.
- Palette fit (weight 0.6) and accessories (`engine.accessory_for`) are in the recommender.

## Colab
Training and eval only (see `colab/README.md`). The Mac runs all live inference.
Clothing data may go to Colab (the owner's decision). Style photos (face and body) never leave the Mac, and neither does the service-role key.

# Closet: working notes

The spec is **SPEC.md** (read it before planning). The look, copy and interactions are in `design-reference/closet-demo.html`.
Work phase by phase (SPEC 12). Plan each phase and get an OK first. Ask before adding paid services or deps that need accounts.
Done: Phase 0 (foundation) and Phase 1 (core wardrobe). Next: Phase 2 (vision).

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
  and `web/lib/jobs.ts` JobKind. `ping` is extra (the round-trip test).
- `wishlist_items.check` from the spec is named `check_result` (CHECK is reserved).
- Next 16 with `cacheComponents`. Read `web/node_modules/next/dist/docs/` before using Next APIs. Middleware is `proxy.ts`.
  Don't call `Date.now()` or `new Date()` during render (it breaks the prerender). Use effects, `useSyncExternalStore`, or event handlers.
- Redirects: route handlers use `relativeRedirect`. The proxy uses `sameHostUrl` (Next normalizes the host).
- Client data goes through `lib/supabase/client.ts` with RLS. Server-only code imports `server-only`.
- Styling: tokens and classes in `web/app/globals.css`, ported from the prototype. No new card kits or gradients.
- Copy: sentence case, typographic apostrophes (’), no “Claude”/AI sparkle words, no arrows in buttons. Errors say what to do.
- Never `dangerouslySetInnerHTML`. Links to outside sites use `target="_blank" rel="noopener noreferrer"`.
- Python: ruff (line 100), mypy strict, handlers idempotent. Raise `TransientError` for retryable failures.
- Secrets: `worker/.env`, `infra/searxng/.env` and `web/.env.local` are gitignored.
  The committed local keys are the public Supabase demo keys.

## Web data layer
- `lib/closet/store.ts` is one client store (useSyncExternalStore). It loads everything once and refetches when the tab
  becomes visible. Writes go through it so local state stays in sync. `useDerived` gives `today` (profile time zone), `byId`, `stats`.
- Atomic writes are RPCs: `log_wear` (the duplicate guard returns 'already'), `save_outfit` (replaces pieces and orders
  by category), `delete_all_my_data` (the client deletes Storage files first).
- The rules are pure functions in `lib/domain/*` (dates, money, wear, rotation, outfit, spend, colors), each with tests.
- Photos: `lib/photos.ts` (1600px + 480px JPEG, EXIF stripped, upload as soon as picked). `lib/signed-urls.ts` batches signed URLs.
- Sheets are addressed by query params (`?item=`, `?add=1`, `?outfit=`, `?edit=`, `?new=1`) through `useSheetParam`.
- e2e: `tests/e2e/data.ts` resets and seeds the owner. Bulk inserts need every key, or missing ones become null.

## Colab
Training and eval only (see `colab/README.md`). The Mac runs all live inference.
Any data may go to Colab (the owner's decision), but the service-role key stays on the Mac.

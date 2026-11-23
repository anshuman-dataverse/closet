# Closet

A personal wardrobe PWA: catalog clothes, pick what to wear, log wears, track spend, hunt deals.
One user, $0 a month by default. Full spec: [SPEC.md](SPEC.md). Look and copy: [design-reference/](design-reference/).

```
iPhone / Mac browser (PWA) → Next.js on Vercel (Hobby) ⇄ Supabase Free ⇐ outbound only ⇐ Mac worker (Python)
```

| Folder | What |
|---|---|
| `web/` | Next.js app (App Router, strict TS). Only public Supabase keys. |
| `supabase/` | Migrations, pgTAP tests, email template, local config |
| `worker/` | Python 3.12 worker for the Mac (uv). Claims jobs, runs models, writes results. |
| `infra/searxng/` | Local metasearch for deal hunts, bound to 127.0.0.1 |
| `colab/` | Training and eval notebooks (Phases 2 and 6) |

## 1. Mac setup (once)

- [uv](https://docs.astral.sh/uv/): `brew install uv`, then `uv python install 3.12`
- Node 24+ and pnpm: `brew install node pnpm`
- Docker Desktop (free for personal use) or Colima: needed for SearXNG and local Supabase
- Supabase CLI: `brew install supabase/tap/supabase`
- Optional: [Ollama](https://ollama.com) for nicer phrasing (2–5 GB per model)
- Later (Phase 5): `pg_dump` matching Supabase's Postgres major (17): `brew install postgresql@17`

The first model run (Phase 2) downloads about 1 GB.

## 2. Supabase (your Free project)

1. `supabase login`, then from the repo root run `supabase link --project-ref <your-ref>` and `supabase db push`.
2. Dashboard → **Authentication → Sign In / Providers**: turn **off** "Allow new users to sign up". Keep Email on.
3. **Authentication → Users → Add user → Create new user** with your email, and tick auto-confirm.
4. **Authentication → Email Templates → Magic link**: paste `supabase/templates/magic_link.html`.
   It includes the 6-digit code, which is how you sign in inside the installed iPhone app.
5. **Authentication → URL Configuration**: set Site URL to your Vercel URL, and add
   `https://<your-app>.vercel.app/auth/callback` to Redirect URLs.
6. Note these down: the Project URL, the **publishable** key (for the web app), the **secret / service-role**
   key (worker only), and your user's id (Users list, for `OWNER_USER_ID`).

**Email (set up):** production sends through Resend SMTP (`[remotes.production.auth.email.smtp]` in
`supabase/config.toml`), so sign-in emails include the 6-digit code. The key lives only in `~/.closet/resend_smtp_key`.
Apply config changes with `RESEND_SMTP_PASS="$(cat ~/.closet/resend_smtp_key)" supabase config push`.

**Free-tier email note:** Supabase's built-in email sender only delivers to your Supabase organization's team
addresses, a few times per hour, and won't accept a custom template. Without the template, emails carry only the
link, not the 6-digit code. To get the code (needed inside the installed iPhone app), add custom SMTP under
**Authentication → Emails → SMTP**, uncomment `[auth.email.template.magic_link]` in `supabase/config.toml`,
and run `supabase config push`.

Production auth settings live under `[remotes.production]` in `supabase/config.toml` and are applied with `supabase config push`.

## 3. Web app on Vercel (Hobby)

Import the GitHub repo in Vercel and set **Root Directory = `web`**. Add 3 environment variables:

```
NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<publishable key>
ALLOWED_EMAIL=<your email>
```

Deploy. Never add the service-role key to Vercel.

## 4. Worker on the Mac

```sh
cd worker
cp .env.example .env        # fill in SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OWNER_USER_ID
uv sync
uv run closet-worker        # foreground; Ctrl-C to stop. Add --fake to return fixtures.
launchd/install.sh          # run at login + restart on crash; logs: ~/Library/Logs/closet-worker.log
launchd/install.sh uninstall
```

Check it from the app: **Profile → Your Mac → Test your Mac**.

The first photo it reads downloads the models, about 770 MB for FashionCLIP and background removal, into `~/.cache`.
After that, a photo takes 1–3 seconds on Apple Silicon.

**Tagging accuracy test:** `uv run closet-worker export-eval`, fix `~/ClosetPhotos/eval/labels.csv`, then run
`colab/tagging_eval.ipynb` on Colab, or `uv run python -m eval.tagging` on the Mac. See `colab/README.md`.

## 5. SearXNG (deal hunts)

```sh
cd infra/searxng
printf 'SEARXNG_SECRET=%s\n' "$(openssl rand -hex 32)" > .env   # once
docker compose up -d                                               # http://127.0.0.1:8888 only
```

Hunts read public product pages on the stores in `worker/closet_worker/vocab/stores.yaml`, honoring
each site's robots.txt, at most one request per second per site. In a live test on 2026-11-22,
11 of 23 stores published readable product data (Gap, Old Navy, Banana Republic, L.L.Bean,
Everlane, Madewell, Taylor Stitch, Buck Mason, Bonobos, Brooks Brothers, Proper Cloth); the rest
block automated reading or only load product data with JavaScript. Hunts name those stores in
their summary. Price watch runs every morning at 09:00 for wishlist items with **Watch price** on.

## 6. iPhone

1. Open your Vercel URL in Safari and sign in.
2. Share → **Add to Home Screen**.
3. Open Closet from the Home Screen. It keeps its own sign-in, so sign in once more
   with the **6-digit code** from the email. The link in the email opens Safari, not the app.

## Local development

```sh
supabase start                  # local stack on ports 554xx (Studio :55423, Mailpit :55424)
cd web && cp .env.example .env.local   # or keep the committed local defaults
pnpm install && pnpm dev:user && pnpm seed && pnpm dev   # seed = sample closet
```

Sign-in emails go to Mailpit at http://127.0.0.1:55424.

## Checks

```sh
cd web    && pnpm check && pnpm e2e         # typecheck, lint, prettier, vitest; playwright
cd worker && uv run ruff check . && uv run mypy && uv run pytest
supabase test db                            # RLS + queue tests (pgTAP)
```

## Backups and restore

The Mac worker backs up **your** data every night at 02:00 (or on the next wake), and whenever
you tap **Back up now** under Your Mac. It needs `pg_dump`/`psql`: `brew install libpq`, and
`DATABASE_URL` in `worker/.env` (Supabase → Connect → direct connection string).

```
~/ClosetBackups/            (only your Mac user can open it)
  db/<UTC stamp>/           your rows from one snapshot: one CSV per table, plus manifest.json
                            (columns, row counts that were checked, SHA-256 per file); 14 kept
  files/<your id>/…         every photo, copied once (photo names never change)
  models/                   installed outfit model, fit gate and garment heads
```

Run one by hand: `cd worker && uv run closet-worker backup`.

**Restore** (into a project that has Closet's schema and doesn't already have your account, for
example a new Supabase project after `supabase db push`, or local after `supabase db reset`):

```
cd worker
CLOSET_RESTORE_DB_URL='postgresql://…'          \
CLOSET_RESTORE_SUPABASE_URL='https://<ref>.supabase.co' \
CLOSET_RESTORE_SERVICE_KEY='…'                  \
uv run closet-worker restore ~/ClosetBackups/db/<stamp> --yes
```

It checks every file's checksum, loads your sign-in record and all tables in one transaction
(triggers off, so nothing is added twice), uploads your photos, then compares row counts with
the backup. The target comes only from those variables, never from `worker/.env`, so a restore
can't overwrite production by accident. `tests/test_backup_integration.py` runs this whole
round trip against local Supabase.

## Cost

Vercel Hobby, Supabase Free, Open-Meteo and everything on the Mac are $0. GPT hunts are optional and blocked
until you raise the paid cap above $0. Supabase Free pauses after about a week of no activity;
daily use and the worker heartbeat keep it awake.

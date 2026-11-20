# Closet: build spec (free, my own models)

This is the full spec for a personal wardrobe and clothing-purchase app that I want you, Claude Code, to build. Read all of it before you plan anything.

**Design reference.** The folder `design-reference/` holds a working prototype:

- `closet-demo.html` opens in any browser with sample data. It shows the target look, copy and interactions. Its data resets on reload.
- `closet.html` is the same prototype built as a claude.ai artifact. Its data layer (`window.claude` db, assets and sample) only exists inside claude.ai, so **don't copy that layer**.
- Replace every "Claude" label in the prototype. This app uses my own models (section 5), not Claude.

**Cost rule: $0 a month by default.**

- The web app runs on Vercel's free Hobby plan.
- The data lives on Supabase's Free plan.
- All machine learning runs on **my Mac** as a background worker.
- The only paid part is optional: my OpenAI (GPT) key. It's used only when I turn on "Search with GPT" for a single deal hunt, and only under a monthly cap that defaults to $0.

---

## 0. How to work on this

1. Work phase by phase (section 12). Start each phase in plan mode: propose the files, schema changes and commands, then wait for my OK.
2. Ask me before you add any paid service, any dependency that needs its own account, or any data this spec doesn't describe.
3. Keep a short `CLAUDE.md` at the repo root, under about 80 lines. It covers:
   - how to run the web app and the worker
   - how to test, lint, migrate and deploy
   - code conventions
   - a pointer to this file
4. After each phase:
   - Run the web checks (typecheck, lint, Vitest, Playwright) and the worker checks (ruff, mypy, pytest).
   - Update `CLAUDE.md` and commit.
   - Give me a short summary plus anything I must do by hand.
5. Never commit secrets. The Supabase service-role key lives only in `worker/.env` on my Mac.

---

## 1. What the app does

It's a mobile-first web app. I install it as a PWA on my iPhone and also use it on my Mac. It's for one user (me), with no social features. It helps me:

- Catalog my clothes with photos. My Mac tags each photo, removes the background and names the colors.
- Decide what to wear for **office, college, party or home**. Picks favor what I've gone longest without wearing, today's weather and my colors. Suggestions come from **my own model, which learns from what I actually wear and like**.
- Log what I wear and see when I last wore each outfit and piece.
- Track my clothing spend against a monthly budget, and see cost per wear.
- Keep a wishlist and get a "Do I need this?" check. It looks for near-duplicates in my closet and counts how many new outfits a piece would add.
- Run **deal hunts**: give an item, an occasion and a dollar range. My Mac searches stores and reads their product pages for price and stock, then ranks the results for me.
- Build a **style profile** from photos of me: undertone, contrast, best colors, colors to use carefully, and fit notes.

---

## 2. Architecture

The app has three parts.

**1. Web app.** Next.js (App Router, strict TypeScript) on Vercel Hobby.

- It renders the UI.
- It handles everything that doesn't need a model: closet, outfits, wear logging, the Today rotation, spend, wishlist and weather.
- It holds only the public Supabase keys.

**2. Supabase Free.**

- Postgres with Row Level Security and the `vector` extension (pgvector).
- Auth with an email magic link.
- Storage, with a private bucket for photos.
- Realtime.
- It also hosts the **job queue** between the app and the worker.

**3. Mac worker.** A Python 3.12 service on my Mac.

- It pulls jobs from Supabase over an outbound connection, runs the models, and writes results back. **Nothing listens on a public port.**
- Vision:
  - `rembg` for background removal.
  - A fashion CLIP model for tags and embeddings. That's FashionCLIP (`patrickjohncyh/fashion-clip`) or Marqo-FashionSigLIP; pick by eval (5.1).
  - MediaPipe Tasks (Face Landmarker, Pose Landmarker).
  - Color clustering.
- Recommender: a candidate generator, a rule scorer, and my personal ranker (scikit-learn first, PyTorch later).
- Shopping: SearXNG (self-hosted metasearch, in Docker, bound to 127.0.0.1), a polite page fetcher, and `extruct` to read schema.org product data.
- Text: templates by default. Ollama (a local LLM) is optional, for nicer phrasing. OpenAI is optional, for GPT hunts only.
- Maintenance: a nightly backup to my Mac, because Supabase Free has no automatic backups.

```
iPhone / Mac browser (PWA)
   │
   ▼
Next.js on Vercel (Hobby) ──── reads/writes, Realtime ────► Supabase Free
                                                              Postgres + pgvector, Auth, Storage, jobs table
                                                                   ▲
                                         outbound only: claim jobs, write results, heartbeat
                                                                   │
                                                   Mac worker (Python, launchd)
                                                   ├─ vision: rembg, fashion CLIP, MediaPipe, colors
                                                   ├─ recsys: candidates, rules, personal ranker
                                                   ├─ shopping: SearXNG (localhost) + fetcher + extruct
                                                   ├─ text: templates, Ollama (optional, localhost)
                                                   └─ optional: OpenAI web search for "Search with GPT" hunts
```

**When my Mac is off or asleep**

- Everything in part 1 still works.
- Model jobs wait in the queue.
- The UI says plainly: "Your Mac is offline. This will run when it's back."

Supabase Free pauses a project after about a week of low activity. Daily use plus the worker's heartbeat keeps it awake.

**Web app environment** (in Vercel and `.env.local`):

```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=     # the project's public (anon / publishable) key
ALLOWED_EMAIL=                     # only I can sign in
```

**Worker environment** (`worker/.env`, on my Mac only, never committed):

```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=         # secret key; lives only on my Mac
DATABASE_URL=                      # direct Postgres connection string, for nightly pg_dump
OWNER_USER_ID=                     # my auth user id; the worker only touches my rows
WORKER_ID=mac
EMBED_MODEL=patrickjohncyh/fashion-clip
DEVICE=auto                        # mps when available, otherwise cpu
SEARXNG_URL=http://127.0.0.1:8888
OLLAMA_URL=http://127.0.0.1:11434  # optional
OLLAMA_MODEL=                      # optional: a small instruct model (about 3–8B parameters)
OPENAI_API_KEY=                    # optional: only for "Search with GPT" hunts
OPENAI_MODEL=                      # optional: pick from OpenAI's current model list
PAID_MONTHLY_CAP_USD=0             # 0 blocks every paid call
BACKUP_DIR=~/ClosetBackups
```

**Layout:**

```
web/                              Next.js app (app/, components/, lib/, tests/)
worker/
  closet_worker/
    main.py                       job loop, heartbeat, scheduler
    jobs/                         one module per job kind
    vision/                       background removal, embeddings, colors, mediapipe
    recsys/                       candidates, scoring, ranker, training
    shopping/                     searxng client, fetcher, product parsing, ranking
    text/                         templates, ollama client
    providers/openai_hunt.py      optional GPT hunts
    vocab/                        types.yaml, colors.yaml, palettes.yaml, staples.yaml, stores.yaml
  tests/   eval/
  pyproject.toml                  (managed with uv)
  launchd/com.closet.worker.plist
infra/searxng/                    docker compose + settings.yml (JSON output on, bound to 127.0.0.1)
supabase/migrations/   supabase/seed.sql
design-reference/
```

**Mac setup** (document it in the README):

- `uv` for Python.
- Docker Desktop (free for personal use) or Colima, for SearXNG.
- Ollama, if I want local phrasing.
- `pg_dump` that matches the Supabase Postgres major version, or `supabase db dump`.
- The first run downloads the models: roughly 1 GB, plus 2–5 GB for an Ollama model.

---

## 3. Data model (Postgres)

**General rules**

- Money is stored as integer **cents** in USD.
- Worn days and bought days are `date` values in my time zone. The time zone is a profile setting that defaults to `America/New_York`.
- Every other time is `timestamptz`.
- Every table has `user_id uuid not null default auth.uid() references auth.users on delete cascade`.
- RLS is enabled on every table. The owner can select, insert, update and delete only where `user_id = auth.uid()`.
- The worker uses the service role, but always filters by `OWNER_USER_ID`.

**Enums**

- `occasion`: `office | college | party | home`
- `item_category`: `Tops | Bottoms | Layers | Shoes | Accessories | Sets & suits` (Layers means jackets, blazers, sweaters, hoodies and coats)
- `item_status`: `active | laundry | retired`
- `job_status`: `queued | running | done | failed`

**profiles** (one row per user; `user_id` is the primary key)

- `sizes` jsonb `{top, waist, inseam, shoe}` (US sizes)
- `fit_pref`: `slim | regular | relaxed | ''`
- `monthly_budget_cents`, `paid_monthly_cap_cents` (default 0)
- `favorite_stores`
- `city_name`, `latitude`, `longitude`, `timezone`, `temp_unit` (`F` or `C`, default `F`)
- `analysis` jsonb (from 5.2), `analyzed_at`
- `undertone_override`, `contrast_override` (nullable; my manual choice wins)
- `created_at`, `updated_at`

**items**

- `id`, `name` (required, 1–80 characters), `category`, `type`
- `color_name`, `color_hex` (check `^#[0-9a-f]{6}$`, nullable), `secondary_color`, `pattern`
- `formality` (1–5), `warmth` (`light | medium | warm`), `occasions occasion[]`
- `brand`, `size`, `price_cents`, `bought_on`, `store`, `notes`
- `photo_path`, `thumb_path`, `cutout_path` (WebP with transparency, from the worker)
- `suggestions` jsonb (worker tags waiting for my review)
- `tags_status`: `none | pending | ready | unsure | not_clothing | failed`
- `status`, `created_at`, `updated_at`

**item_embeddings**

- `item_id` (primary key), `model`, `embedding vector(512)`, `created_at`
- The dimension must match the chosen model: 512 for FashionCLIP. Change it if eval picks another model.
- No ANN index is needed for a few hundred rows.

**outfits**: `id`, `name`, `occasions occasion[]`, `source` (`manual | suggested`), `created_at`, `updated_at`.

**outfit_items**: `outfit_id`, `item_id`, `position`. Primary key `(outfit_id, item_id)`.

**wear_logs**: `id`, `worn_on date`, `occasion`, `outfit_id` (nullable), `created_at`. A unique index on `(user_id, worn_on, outfit_id)` where `outfit_id` is not null.

**wear_log_items**: `wear_log_id`, `item_id`. This snapshot of what I wore keeps stats correct after an outfit is edited.

**wishlist_items**

- `id`, `name`, `category`, `color_name`, `occasion`
- `price_cents`, `url`, `store`, `notes`, `photo_path`, `image_url` (from hunts)
- `embedding vector(512)`
- `status` (`wanted | bought | removed`)
- `check` jsonb (from 5.6), `checked_at`
- `watch` bool, `target_price_cents`
- `last_seen_price_cents`, `last_price_check_at`
- `created_at`

**hunts**

- `id`, `query`, `occasion`, `budget_min_cents`, `budget_max_cents`, `notes`
- `use_gpt` bool (default false), `provider` (`free | gpt`)
- `status` (`job_status`), `summary`, `error`
- `pages_checked`, `created_at`, `started_at`, `finished_at`

**hunt_results**

- `id`, `hunt_id`, `rank`, `title`, `store`, `url`, `image_url`
- `price_cents`, `was_price_cents`, `rating`, `rating_count`
- `why`, `quality`, `size_available` (`yes | no | unknown`), `checked_at`

**style_photos**: `id`, `photo_path`, `kind` (`front | side | back | face | other`), `created_at`.

**jobs**

- `id`, `kind`, `payload` jsonb, `status`, `result` jsonb, `error`
- `attempts`, `priority`, `worker_id`
- `created_at`, `started_at`, `finished_at`
- Kinds: `tag_item`, `embed_wish`, `analyze_profile`, `suggest_outfits`, `check_wish`, `find_gaps`, `run_hunt`, `price_check`, `train_ranker`, `backup`.

**workers**: `id` (text), `last_seen_at`, `version`, `capabilities` jsonb (`{searxng, ollama, openai}`).

**suggestion_events**: `id`, `occasion`, `item_ids uuid[]`, `context` jsonb (weather and note), `score`, `model_version`, `action` (`shown | worn | saved | skipped | liked | disliked`), `created_at`.

**model_versions**: `id`, `kind` (`ranker | compat`), `sample_count`, `metrics` jsonb, `artifact_path`, `active`, `trained_at`.

**price_checks**: `id`, `wishlist_id`, `checked_at`, `price_cents`, `in_stock`, `source` (`jsonld | opengraph | gpt`), `note`.

**paid_usage**: `id`, `feature`, `model`, `input_tokens`, `output_tokens`, `web_search_calls`, `est_cost_usd`, `created_at`.

**Functions**, callable only with the service role:

- `claim_job(p_worker text)` picks the highest-priority, oldest queued job using `for update skip locked`, marks it running, and returns it.
- `requeue_stale_jobs()` handles jobs that have been running for more than 10 minutes. Ones with fewer than 3 attempts go back to queued; the rest are marked failed.

**Views** use `with (security_invoker = true)`:

- `item_stats` (wear count, last worn, cost per wear)
- `outfit_stats`
- `monthly_spend`

**Storage** uses a private bucket named `wardrobe`. Paths:

- `{user_id}/items/{item_id}/{uuid}.jpg`, plus `_thumb.jpg` and `_cutout.webp`
- `{user_id}/style/{uuid}.jpg`
- `{user_id}/wishlist/{id}/{uuid}.jpg`

Policies allow access only when the first path segment equals `auth.uid()`. Images are shown through batched, short-lived signed URLs. Deleting a row deletes its files.

---

## 4. Screens and behavior

### Navigation

- On phones: a bottom tab bar (Today, Closet, Outfits, Shop, Spend) and a profile button in the header. At 900px and wider: top tabs.
- Routes: `/today` (the default), `/closet`, `/outfits`, `/shop?tab=wishlist|hunts|missing`, `/spend`, `/profile`.
- Forms open in a bottom sheet (a modal dialog) with a sticky action bar.
- **Worker status:** when the worker's `last_seen_at` is more than 2 minutes old, show a small "Mac offline" pill in the header. Tapping it explains what is waiting and what still works.

### 4.1 Today

- The header shows the date and a weather line, such as "38° to 47°F, 70% chance of rain".
- The occasion picker (office, college, party, home) is the hero (section 7). Remember the last choice on the device.
- **Pick card**
  - It uses saved outfits for this occasion, leaving out any with retired or in-laundry pieces.
  - Order is by last worn, oldest first, with never-worn first and ties broken by `created_at`.
  - It shows a flat-lay of the pieces (cutouts when available), the name, a hang tag ("Last worn 12 days ago" or "Never worn") and the wear count.
  - Buttons: **Wear this**, **Next option** and **Details**.
  - This works without the worker.
- **Wear this** writes `wear_logs` plus `wear_log_items`, then shows a "Logged for today" toast with **Undo**. Logging the same outfit twice on the same day shows "Already logged for today" and does nothing.
- If I've already logged an outfit today for the selected occasion, show a "You're wearing" card with **Pick something else** and **Remove from log**.
- **More ideas** (5.4)
  - It has an optional note field, for example "client meeting at 2".
  - Each idea card offers:
    - **Wear today**: saves the idea as an outfit with source `suggested`, then logs it.
    - **Save outfit**
    - **Not today** (a skip)
    - thumbs up and thumbs down (aria-labels "Good idea" and "Not for me")
  - Every action writes a `suggestion_events` row. That's my training data.
  - When the Mac is offline, show: "Your Mac is offline, so new ideas will appear when it's back. Your saved outfits still rotate."
- **Recently worn** lists the last 6 entries. Entries from today and yesterday have **Remove**.
- Empty states lead to Add clothes or Build an outfit.

### 4.2 Closet

- **Add clothes sheet**
  1. I take or choose a photo.
  2. The client resizes it and strips EXIF (section 6), then uploads it right away.
  3. The app queues a `tag_item` job and waits up to 20 seconds, with the message "Reading your photo…".
  4. When suggestions arrive, they fill only the fields I haven't touched.
  5. If the tag is unsure, say "Not sure about this one. Check the type." If it isn't clothing, say "That doesn't look like clothing. Try another photo."
  6. If the Mac is offline, say "Save it now, and the details will be suggested when your Mac is back."
  7. Fields: name (required), category, type, color (with a swatch), pattern, good for (occasions), formality, warmth, price paid, bought on, brand, size, store and notes.
- **Grid**
  - Square tiles. A piece with no photo shows a color swatch and a hanger icon.
  - Each tile shows the name, and "5 wears, last Nov 17" or "Not worn yet".
  - Filters: category, occasion, and status (Active, In laundry, Retired).
  - Sorts: Recently added, Longest since worn, Least worn, Most worn, and Price high to low.
- **Item sheet**
  - Stats: the hang tag, wears, cost per wear, and the outfits the piece is in.
  - Pending suggestions, with **Apply**.
  - Editable fields, and a photo/cutout toggle.
  - **In laundry**, **Retire** / **Bring back**, and **Delete**. Delete takes two taps, removes the piece from outfits, and deletes its files.
- **Laundry done** returns every laundry piece to active.

### 4.3 Outfits

- **Builder**
  - Tap pieces, grouped by category. A selected piece gets an ink border, a chalk ring and a check mark.
  - The name is optional; the default joins the first two pieces with " + ".
  - Pick the occasions. At least 2 pieces and 1 occasion are required.
  - Pieces are ordered: Tops, Sets & suits, Layers, Bottoms, Shoes, Accessories.
- **List**: least recently worn first, with an occasion filter. Each card shows a flat-lay, the name, a hang tag, occasion pills, **Wear today** and **Edit**.
- **Detail sheet**
  - The pieces, each linking to its item.
  - **Wear it**: pick an occasion, then today or a past date.
  - History, with **Remove** on each entry.
  - **Edit** and **Delete**.

### 4.4 Shop: Wishlist, Deal hunts, What's missing

**Wishlist**

- The add form has: name (required), category, color, occasion, price, store, link, notes, and an optional photo or screenshot.
  - Add `https://` to the link if it's missing, and reject anything that isn't http(s).
  - **Watch price** (5.9).
- Each card shows:
  - The item details and **Open listing**.
  - A local overlap note, such as "You own 3 similar: …". This uses text rules right away and embeddings once the worker has run.
  - The verdict, once it's checked.
- Card buttons:
  - **Do I need this?** (5.6)
  - **I bought it**: opens Add clothes prefilled (photo included) and marks the wish as bought.
  - **Remove**, with Undo.

**Deal hunts**

- **New hunt** fields: what (required), occasion, budget from and to (swap them if reversed), and notes.
  - My sizes, fit, colors, favorite stores and city are attached automatically.
  - A **Search with GPT** toggle appears only when the worker reports OpenAI capability and my paid cap is above $0. Its note: "Uses your OpenAI key. Small cost per hunt."
- **Card**
  - Status: Queued, Waiting for your Mac, Searching…, N picks, or Failed with the reason and **Retry**.
  - A one-line summary.
  - Ranked picks. Each shows:
    - the product image, from the store's image URL
    - the title, linking to the store page
    - the store
    - the price, with the original price struck through and a "% off" badge
    - why it suits me and the quality notes (rating and count)
    - size availability and "Checked {time}"
  - Each pick has **Add to wishlist**.
- Hunt actions: **Run again** and **Delete** (with Undo).
- Copy to show:
  - "Prices change. Check the store page before buying."
  - For free hunts: "Free search reads public product pages. Some stores block it, so results vary."

**What's missing**

- Pick an occasion and tap **Find what's missing** (5.7).
- It shows 3–5 ideas, each with a price range and a reason.
- Each idea offers **Start a hunt** (prefilled) and **Add to wishlist**.

### 4.5 Spend

- **This month**
  - A big number for this month's spend, labeled "of your $150 budget".
  - A meter with a chalk fill, red when over.
  - "$X left this month" or "$X over budget".
- **Last 12 months**: a bar chart with the current month in chalk, plus the total.
- **By category**: spend for the last 12 months.
- **Earning their keep**: the lowest cost per wear among pieces with 2 or more wears (top 5).
- **Waiting for a wear**: pieces worn once or never and bought at least 30 days ago (or with no date), most expensive first (top 5).
- A note saying how many pieces have no price or date.
- **Paid usage this month**, against the cap. Hide this section when the cap is $0.

### 4.6 Profile

- **Style photos**
  - Up to 6: front, side and back in fitted clothes, plus a face close-up in daylight with no filter.
  - Upload, or remove with two taps.
  - The note: "Your photos are analyzed on your Mac and never sent to an AI service."
- **Analyze my photos** (5.2) produces a "What suits you" section:
  - the summary, plus undertone and contrast pills
  - pinked swatches for best colors, neutrals, and colors to use carefully (each with its reason)
  - fit notes and tips by occasion
  - a confidence note when the lighting was poor
  - **Change** controls to override undertone and contrast
  - the note: "An estimate from your photos. You can change it."
- **Your picks model** (5.5)
  - It shows how many choices it learned from, when it was last trained, and how it compares to the rules alone.
  - **Retrain now** queues training.
  - Before there's enough data, say: "Keep logging what you wear. After about 50 choices, your picks start learning from you."
- **Settings**
  - Sizes (US), fit preference, monthly clothing budget, and the paid cap (default $0).
  - Favorite stores.
  - Home city, geocoded with Open-Meteo; time zone; °F or °C.
  - Worker status and last backup.
  - **Delete all my data**, after a typed confirmation.

---

## 5. Models and pipelines (the Mac worker)

### 5.0 Worker basics

- **Stack:** Python 3.12, managed with `uv`. Libraries:
  - `supabase` (Python client), `httpx`, `pydantic`
  - `numpy`, `pillow`, `opencv-python-headless`, `scikit-image` (CIELAB and ΔE2000), `scikit-learn`
  - `torch`, `open_clip_torch` or `transformers` (for the fashion CLIP model)
  - `rembg`, `mediapipe`, `extruct`, `pyyaml`
- **Job loop**
  - Upsert a heartbeat to `workers` every 30 seconds, including capabilities (SearXNG reachable, Ollama reachable, OpenAI key present).
  - Call `claim_job` every 3 seconds and dispatch to the handler for that job kind.
  - Each job kind has its own timeout.
  - Write the result or error. Retry transient errors up to 3 times with backoff.
- **Models** load lazily and stay in memory. Use MPS when available, otherwise CPU.
- **Scheduler** (runs only while the Mac is awake; catch up on wake):
  - Every 10 minutes: `requeue_stale_jobs`.
  - 09:00 daily: price checks.
  - 02:00 nightly, or the next wake: `train_ranker` and `backup`.
- **launchd agent** `com.closet.worker.plist`: starts at login, restarts after a crash, and logs to `~/Library/Logs/closet-worker.log`.
- **`--fake` mode** returns fixtures right away. Use it for e2e tests and for building the web app without the models.
- Handlers are idempotent: running a job again overwrites its own results.

### 5.1 Photo tagging (`tag_item`)

1. Download the 1600px JPEG from Storage.
2. Run `rembg` to get a mask.
   - Save a cutout as WebP with alpha (`cutout_path`).
   - Crop to the mask's bounding box with 5% padding.
3. Embed the crop with the fashion CLIP model, L2-normalized, and upsert it into `item_embeddings`.
4. **Type (zero-shot).** Score text prompts of the form "a photo of a {type}" for every entry in `vocab/types.yaml`. The list has about 80 types, for example:
   - Tops and layers: oxford shirt, dress shirt, polo shirt, t-shirt, henley, flannel shirt, overshirt, crew sweater, v-neck sweater, cardigan, hoodie, sweatshirt
   - Jackets and coats: blazer, suit jacket, bomber jacket, denim jacket, puffer jacket, wool overcoat, trench coat, rain jacket
   - Bottoms: chinos, dress trousers, jeans, joggers, shorts
   - Shoes: sneakers, running shoes, loafers, oxford shoes, derby shoes, chelsea boots, boots, sandals
   - Accessories: belt, watch, cap, beanie, scarf, tie, backpack
   - Sets and other: kurta, nehru jacket, suit, tracksuit, and so on

   Each type maps in the YAML to a category, a default formality (1–5), a warmth and default occasions.
5. **Pattern (zero-shot).** Choose among solid, striped, checked, printed and textured.
6. **Color.**
   - Run k-means (k=3) on the mask pixels in CIELAB. The largest cluster is the primary color.
   - Name it by the nearest entry in `vocab/colors.yaml`, about 40 named colors with hex values, using ΔE2000.
   - Keep a secondary color if it covers at least 20% of the piece.
7. **Name.** Combine primary color and type, for example "Navy oxford shirt".
8. **Confidence.**
   - If the top-1 type probability is below 0.35, mark it `unsure`.
   - Compare "a photo of clothing" with "a photo of something that is not clothing". If the second wins, mark it `not_clothing`.
9. Write `items.suggestions` and `tags_status`.

**Evaluation** (`eval/tagging.py`)

- I'll hand-label 50 of my photos in a CSV.
- Report accuracy for category, type, pattern and color, plus a confusion matrix.
- Compare FashionCLIP with Marqo-FashionSigLIP, then set `EMBED_MODEL` to the winner.
- Targets: at least 90% on category and 70% on type.

### 5.2 Style profile (`analyze_profile`)

This needs the face close-up and a front full-body photo. Side and back photos are optional. It runs entirely on my Mac.

1. **Skin color.** Run Face Landmarker on the close-up and take skin regions on both cheeks and the forehead, avoiding eyes, brows and lips. Use the median CIELAB value.
2. **Undertone and depth.**
   - Undertone comes from the hue angle h = atan2(b*, a*) in bands: warm, neutral or cool. It's olive when a* is low and b* is moderate.
   - Depth comes from L* (and ITA°).
   - Keep the thresholds in config and tune them on a few reference photos.
3. **Contrast.** Compare hair L* (a region above the forehead landmarks) with skin L*:
   - low below 25
   - medium from 25 to 45
   - high above 45
   - tune these thresholds too
4. **Lighting check.** If the face is very dark, has a strong color cast, or has blown highlights, write a `confidence_note`, for example "Lighting looks warm and dim. Retake near a window for a better read."
5. **Palette.** Look up `(undertone, depth, contrast)` in `vocab/palettes.yaml` to get:
   - best colors (6–8)
   - neutrals (3–5)
   - colors to use carefully (2–4, each with a short reason)

   You draft this table from common seasonal color guidance, and I review it.
6. **Fit.** Run Pose Landmarker on the front photo and measure:
   - shoulder width (landmarks 11–12) and hip width (23–24)
   - torso length (shoulder midpoint to hip midpoint) and leg length (hip to ankles 27–28)

   Turn the ratios into fit notes from templates. The language must stay neutral and practical: **never comment on weight or attractiveness, and never suggest changing the body.**
7. **Summary and occasion tips** come from templates. Ollama may rephrase them, using facts only.
8. **Save** to `profiles.analysis`, including the measurements and thresholds used. Overrides win when set.

### 5.3 Weather (web app)

- Geocode my city with Open-Meteo. Read the daily high and low, precipitation probability and weather code in my unit and time zone.
- Cache it for 1 hour, and include it in job payloads.
- If weather fails, Today still works without the weather line.

### 5.4 Outfit ideas (`suggest_outfits`)

**Inputs:** occasion, date, weather and an optional note.

1. **Eligible pieces.** Active (not in laundry or retired), and either tagged for the occasion or within its formality range:

   | Occasion | Formality |
   |---|---|
   | Office | 3–5 |
   | College | 2–4 |
   | Party | 2–5 |
   | Home | 1–3 |

2. **Candidates.**
   - A top plus a bottom, or a set.
   - Plus shoes, if any are eligible.
   - Plus a layer when the high is below 60°F or rain chance is at least 50%.
   - If there are more than 5,000 combinations, sample them.
3. **Rule score** (weights live in config):
   - **Color harmony** on the primary colors, in CIELAB: neutrals go with anything, use at most two saturated hues, and give a small bonus to analogous or complementary pairs.
   - **Palette fit:** closeness to my best colors and neutrals, with a penalty for "use carefully" colors on tops and layers, since those sit near the face.
   - **Formality:** small spread within the outfit, and close to the occasion's target.
   - **Weather:** warmth against temperature, and a rain penalty for suede and white sneakers.
   - **Freshness:** favor pieces I haven't worn lately. Penalize pieces worn in the past 2 days, and the exact outfit if worn in the past 7 days.
   - **Note rules:**
     - "meeting", "presentation" or "interview" raises formality by 1
     - "gym", "lazy" or "home" lowers it by 1
     - "rain" or "snow" sets the weather
     - If Ollama is available, it can turn the note into the same constraints as JSON. Otherwise, use keyword rules.
4. **Blend in the personal ranker** (5.5) when one is active.
5. **Pick 3 with diversity:** each new pick shares at most one piece with earlier picks.
6. **Reasons** are structured (freshness, palette, weather, formality). Templates turn them into one sentence, for example: "Navy and grey is a classic pairing, and you haven't worn the shirt in 12 days. The sweater handles 41°F."
7. **Log** each idea as a `suggestion_events` row with action `shown`. The web app logs whatever I do next.

### 5.5 Personal ranker (`train_ranker`): the model that learns me

- **Labels**
  - Positive: worn, saved, liked, and outfits I build myself and wear.
  - Negative: skipped and disliked.
  - Weak negative (weight 0.3): ideas shown with no action.
- **Features**
  - Per-slot embeddings (top, bottom, shoes, layer; zeros when a slot is empty), each reduced to 32 dimensions with PCA.
  - The rule-score features, an occasion one-hot and the temperature.
- **Model**: logistic regression first; a small PyTorch MLP once there are 300 or more labeled examples.
- **When it trains**: nightly, once there are at least 50 labeled examples and at least 10 new ones since the last run.
- **Validation**
  - Time-based split: train on the oldest 80% and validate on the newest 20%.
  - Metrics: AUC and top-3 hit rate, compared with the rules-only baseline on the same split.
- **Activation guardrail**: switch a model on only if it beats the baseline.
  - Record every run in `model_versions`.
  - Keep artifacts in `~/.closet/models/` and include them in backups.
- **Blending**: final = (1 − α)·rules + α·ranker, where α = min(0.7, n/500).
- **Profile line**, for example: "Learned from 214 of your choices. Last trained Nov 20. Picks what you wear 18% more often than the rules alone."

### 5.6 Do I need this? (`check_wish`)

1. **Embed the wishlist item.** Use its image (my upload, or the hunt's `image_url`) when there is one. Otherwise use the text "a photo of a {color} {name}". Store the embedding.
2. **Near-duplicates.** Find the nearest owned items in the same category by cosine similarity (pgvector).
   - It's a duplicate when similarity is at least τ.
   - For image-to-image matches, τ is about 0.90; text-to-image needs a lower value. Calibrate both in eval.
3. **Unlocks.** Run the 5.4 candidate generation for the item's occasion, with and without the item. Count the new outfits that score above the threshold.
4. **Budget.** Compare this month's spend plus the price with my monthly budget.
5. **Verdict.**
   - **skip**: it duplicates a piece I wear, or it puts me over budget.
   - **buy**: there's no duplicate, it unlocks 3 or more outfits, and it's within budget.
   - **wait**: anything else.
6. **Reasons** come from templates, for example "You own 2 very similar shirts and wear one of them weekly."
7. **Save** to `wishlist_items.check`.

### 5.7 What's missing (`find_gaps`)

1. `vocab/staples.yaml` lists about 150 staple pieces. Each has a type, category, formality, warmth and typical US price range.
2. For the chosen occasion, pair each staple with colors from my palette. Skip near-duplicates of what I own.
3. Embed each idea with the fashion CLIP **text** encoder, simulate adding it, and count the new good outfits it creates (using 5.4 scoring).
4. Return the top 5, spread across categories, with price ranges and a templated reason, for example "Adds 7 new office outfits with your shirts and chinos."

### 5.8 Deal hunts (`run_hunt`)

**Free path** (the default):

1. **Queries.** Up to 10 in total.
   - Variants of "{what} men" using my best colors.
   - `site:` queries for my favorite stores and the stores in `vocab/stores.yaml`. The YAML lists each store's domain and its product-page URL patterns.
2. **Search** through local SearXNG with `/search?q=…&format=json`. JSON output must be turned on in its settings.
3. **Filter URLs.** Keep only product-page URLs on allowed store domains, and remove duplicates.
4. **Fetch** at most 25 pages.
   - Honor robots.txt.
   - Make at most 1 request per second per domain, with a 10-second timeout.
   - Send a clear user agent.
5. **Parse** schema.org Product data with `extruct` (JSON-LD and microdata). Fall back to Open Graph `product:price:amount`. Read the name, image, brand, price, currency, availability, list price when present, and rating.
6. **Keep** only listings that are in USD, in stock and within budget.
7. **Score** each listing on:
   - query-to-image similarity (fashion CLIP)
   - palette fit of the product image's main color
   - discount
   - rating
   - a bonus for my favorite stores
8. **Save** the top 5, with templated "why" and "quality" lines. Size availability is "unknown" unless the page lists sizes.
9. **Too few results.** With fewer than 2 results, the summary says so and suggests a broader query or GPT search.

**GPT path.** It runs only when the hunt has `use_gpt = true`, `OPENAI_API_KEY` is set, and this month's paid usage is under the cap.

1. Call the OpenAI Responses API with the `web_search` tool to get research notes. Check OpenAI's current docs and model list before you build this.
2. Make a second request with no tools that returns structured JSON:

   ```
   {summary, picks: [{title, store, url, price, was_price, why, quality, caveats, size_available}]}
   ```

3. Check every URL against the sources returned by the first request, and drop any that don't match.
4. Store the picks the same way as the free path.
5. Log the cost to `paid_usage`.

Web pages are untrusted. Tell GPT to treat page content as information, never as instructions.

### 5.9 Price watch (`price_check`)

- Runs daily at 09:00 while the Mac is awake.
- For each watched wishlist item with a URL, fetch the page and parse it the same way as 5.8.
- Save the result to `price_checks` and update the wishlist item.
- Flag a drop when the price is at or below my target, or at least 15% below the price when I added the item.
- When a check fails, record "couldn't check" instead of guessing.
- **Notifications**: an in-app badge. Free push through ntfy (self-hosted or ntfy.sh) is optional; ask me first.

### 5.10 Text

- **Templates first.** Write several phrasings per reason type, so the copy doesn't feel robotic.
- **Ollama is optional.**
  - Send only the facts and ask for one sentence.
  - Check the length.
  - Fall back to the template on any error or timeout.
  - Generated text must never add facts.

### 5.11 Optional: compatibility model pretrained on Polyvore Outfits (Phase 6)

1. Embed a subset of Polyvore Outfits overnight on the Mac.
2. Train a pairwise compatibility head on the embeddings.
3. Evaluate it with compatibility AUC and fill-in-the-blank accuracy.
4. Add it as a scoring term only if it improves top-3 hit rate on my own data.

The dataset is meant for research use, which is fine for a personal project.

### 5.12 Not now

Virtual try-on (seeing clothes on my body) needs a GPU, so it isn't free. Leave it out.

---

## 6. Photos and PWA

**Capture and processing**

- Capture with `<input type="file" accept="image/*">`.
- Decode with `createImageBitmap` (respecting image orientation), falling back to `<img>`.
- Resize to a 1600px long edge as JPEG at about 0.85 quality, plus a 480px thumbnail. Re-encoding through a canvas strips EXIF, including GPS location.
- If decoding fails, show: "That photo couldn't be opened. Try a JPEG or PNG."

**Upload and display**

- Upload right away and queue the `tag_item` job.
- Flat-lays use the worker's cutout (transparent background on the `--paper` panel) when it exists, and the photo otherwise.

**PWA**

- Manifest: name "Closet", standalone display, theme colors from the tokens.
- Icons at 192 and 512 pixels, a 180-pixel Apple touch icon, and the iOS meta tags.
- `viewport-fit=cover` plus safe-area padding.
- It must work from my Home Screen.

**Storage budget**

- Each piece takes roughly 0.5 MB (photo, thumbnail and cutout).
- A few hundred pieces fit easily in the free 1 GB.

---

## 7. Design system (match the prototype)

**Look:** a cool oxford-shirting background, raw-denim ink, and a tailor's-chalk yellow accent. Photos are the content. Everything else stays quiet.

**Tokens**

| Token | Light | Dark |
|---|---|---|
| `--paper` | `#E6EBF1` | `#10131C` |
| `--card` | `#FFFFFF` | `#181D2A` |
| `--sunk` | `#D5DCE6` | `#232A3B` |
| `--ink` | `#1A2142` | `#E8ECF4` |
| `--ink-2` | `#525C76` | `#A2ABBF` |
| `--line` | `#C3CCD8` | `#2C3448` |
| `--chalk` | `#F4C430` | `#F4C430` |
| `--chalk-ink` | `#1A2142` | `#1A2142` |
| `--mark` (highlight band) | `#F4C430` | `rgba(244,196,48,.36)` |
| `--sale` | `#C3372B` | `#FF7A6B` |
| `--good` | `#1E7650` | `#57C997` |
| `--wait` | `#8A5E00` | `#E8B84B` |
| `--focus` | `#2F6FED` | `#86A9FF` |

Follow the system's light or dark setting, and give `body` an explicit background.

**Type**

- One family: **Archivo** (Google Fonts), loaded as a variable font with the width axis (wdth 62–125, wght 100–900).
- Wordmark: lowercase "closet", wdth 125, weight 800.
- Page titles: wdth 125, weight 800, tight tracking.
- Body: wdth 100, weight 400.
- Small labels: about wdth 88–92, weight 600.
- Inputs: at least 16px, so iOS doesn't zoom.

**Signature elements**

- **Occasion picker**
  - Four stacked words: office, college, party, home.
  - Unselected words: wdth 62, weight 300, 60% opacity.
  - Selected word: wdth 125, weight 820, with a `--mark` band behind 60–88% of its height.
  - Animate `font-variation-settings` over 0.5s with `cubic-bezier(.2,.75,.2,1)`, and turn the animation off under `prefers-reduced-motion`.
  - Use `radiogroup` semantics with arrow-key support.
  - On desktop, Today becomes two columns, with the picker sticky on the left.
- **Hang tag** for last-worn facts: a chalk fill, `clip-path: polygon(10px 0,100% 0,100% 100%,10px 100%,0 50%)`, and a small round "punched hole" in the card color.
- **Flat-lay**: 1–4 pieces on a `--paper` panel. With 3 pieces, one tall photo goes on the left and two squares on the right. Pieces without a photo show their color swatch with the name.
- **Pinked swatches**: color chips with a zigzag bottom edge (done with clip-path).
- **Controls and feedback**
  - Pill chips and buttons; buttons at least 44px tall.
  - The primary button uses an ink fill, and so does a pressed chip.
  - Bottom sheets on phones; centered dialogs at 700px and up.
  - Toasts with **Undo**.
- **"Mac offline" pill**: uses `--wait`, sits small in the header, and appears only while the Mac is offline.

**Avoid**

- generic SaaS card kits with identical shadows
- all-caps or eyebrow labels
- arrows in button text
- monospace data labels
- decorative gradients
- any "AI" sparkle language
- "Claude" anywhere in the UI

**Copy**

- Sentence case and plain verbs.
- One name per action. "Wear this" leads to "Logged for today".
- Empty states invite an action.
- Errors say what happened and what to do.
- Use typographic apostrophes in UI text.

**Accessibility**

- Visible focus rings.
- Labels on every input.
- Alt text on photos, left empty where the name is printed below.
- AA contrast in both themes.

---

## 8. Domain rules (pure functions with tests, on both sides where needed)

- **Wear counts and last worn:** from `wear_log_items` for pieces and `wear_logs` for outfits.
- **Rotation order:** as described in 4.1.
- **Cost per wear:** price / max(1, wears).
- **Text-only "similar" check** (before embeddings exist):
  - The pieces share a category and a significant word from the type or name.
  - Ignore color words and generic words: slim, regular, relaxed, fit, classic, cotton, stretch, casual, formal, long, short, sleeve, men, mens.
  - List color matches first.
- **Money:** "$35" and "$39.50". Budget ranges: "$25 to $60", "up to $60" or "from $25".
- **Dates:** "Never worn", "Worn today", "Worn yesterday" or "Last worn 12 days ago". Day boundaries use my time zone.
- **URLs:** normalize them and allow only http(s). Open links with `target="_blank" rel="noopener noreferrer"`.

---

## 9. Security and privacy

- RLS on every table, storage policies scoped to each user's folder, and views with `security_invoker`.
- Only `ALLOWED_EMAIL` can sign in. Turn off open sign-ups in Supabase Auth, and check the email on the server too.
- Vercel holds only public keys.
  - The service-role key and `DATABASE_URL` live only in `worker/.env` on my Mac.
  - The worker filters every query by `OWNER_USER_ID`.
- Nothing on my Mac listens on a public port. SearXNG and Ollama bind to 127.0.0.1.
- My photos are processed on my Mac and never sent to an AI service. Their EXIF data is stripped.
- Free hunts send only search queries to search engines, through SearXNG. GPT hunts send only the hunt request (query, budget, sizes, colors, stores, city).
- Render all web text as plain text. Never use `dangerouslySetInnerHTML` for scraped or generated text.
- "Delete all my data" removes every row and every stored file.

---

## 10. Backups

Supabase Free has no automatic backups, so the worker backs up every night:

- `pg_dump` of my data to `BACKUP_DIR`, keeping the last 14 dumps.
- A sync of new Storage files into `BACKUP_DIR/files/`.
- Model artifacts.

The profile shows "Last backup: …". Document a restore script in the README.

---

## 11. Testing

**Web (Vitest)**

- the section 8 rules
- the job status flows
- the rotation

**Web (Playwright)**

- Runs at a phone size (390×844) and on desktop (1280), against the worker in `--fake` mode.
- Flows:
  1. Add a piece with a photo fixture; suggestions arrive; save.
  2. Build an outfit.
  3. Today: pick, wear, undo, then confirm the duplicate guard.
  4. More ideas: save one, wear one, thumbs down one (events recorded).
  5. Wishlist: add, check, then "I bought it" moves it into the closet.
  6. Hunt: create it, the fake worker finishes it, add a pick to the wishlist.
  7. Offline state: stop the fake worker heartbeat and confirm the "Mac offline" pill and the queued jobs.
  8. Spend totals.
  9. Profile overrides.
  10. Dark mode.
  11. No console errors.

**Worker (pytest)**

- ΔE2000 color naming.
- Color extraction on synthetic images.
- Lab conversion.
- Landmark-ratio math with fake landmarks.
- Palette lookup.
- Candidate generation constraints.
- Each scoring term.
- Diversity selection.
- Ranker training on synthetic data: it beats random, and the guardrail blocks a worse model.
- Product parsing on 5–10 product pages saved as HTML fixtures (no live network in tests).
- Store URL filters and robots.txt handling.
- Job claim, requeue and idempotency.
- Templates.

**Eval scripts**

- `eval/tagging.py` (5.1)
- `eval/ranker.py`, which prints the metrics from 5.5 on my real data

---

## 12. Build phases

**Phase 0: Foundation**

- Web app shell:
  - strict TypeScript, ESLint and Prettier
  - the Supabase schema, including `jobs`, `workers` and pgvector
  - auth, routes with empty states, tokens and font, tab bars, the Sheet and Toast components, and the PWA files
- Worker skeleton: uv project, heartbeat, claim loop, `--fake` mode and the launchd agent.
- SearXNG docker compose, bound to localhost.
- README with the setup steps.
- Done when:
  - I can sign in on my iPhone and add the app to my Home Screen
  - the "Mac offline" pill reflects the worker correctly
  - a test job makes a round trip

**Phase 1: Core wardrobe (no models)**

- Pieces with the photo pipeline, grid, filters, sorts, laundry, retire and delete.
- Outfits.
- Wear logging with Undo and the duplicate guard.
- Today rotation and Recently worn.
- Spend, profile settings and the seed script.
- Done when the non-model e2e flows pass, and I can add 10 pieces on my phone in under 5 minutes.

**Phase 2: Vision**

- Tagging, cutouts, embeddings, color naming and the eval script.
- "Fill in from photo", suggestions with **Apply**, and cutouts in flat-lays.
- Done when the eval meets the 5.1 targets on my labeled photos.

**Phase 3: Recommender**

- Weather, candidates, rule scoring, More ideas with feedback events, Do I need this? and What's missing.
- Done when ideas never break the structure rules and repeats within 7 days are penalized (both tested).

**Phase 4: Style profile**

- The MediaPipe pipeline, the palettes table, fit templates and overrides.
- Palette fit wired into scoring.

**Phase 5: Shopping and safety**

- Free hunts, price watch and backups.
- Optional GPT hunts with the paid cap.
- Done when a hunt for "white oxford shirt, office, $25–$60" returns in-budget picks from at least 2 stores, or gives an honest message when the stores block it.

**Phase 6: Learning**

- Personal ranker training, the activation guardrail and the model stats on the profile.
- Optional Ollama phrasing.
- Optional Polyvore compatibility model.

**Phase 7: Extras** (ask me which order)

- A week planner: plan the next 7 days by occasion without repeats.
- Offline read-only mode.
- Data export (CSV or JSON).
- ntfy push.

**Every phase is done when:**

- all checks are green
- phone, desktop and dark mode are verified
- there are no console errors
- focus, labels and contrast are checked

---

## 13. What it costs

| Part | Cost |
|---|---|
| Vercel Hobby | $0 (personal, non-commercial use) |
| Supabase Free | $0. Limits: 500 MB database, 1 GB file storage, 5 GB egress. It pauses after about a week of no activity and has no automatic backups (the worker backs up). |
| Worker, models, SearXNG, Ollama | $0 (runs on my Mac) |
| Open-Meteo weather | $0 |
| GPT hunts | Optional, pay-per-use, blocked unless I raise the cap above $0 |

---

## 14. Not in scope

- multiple users or sharing
- social feeds
- affiliate links
- automatic buying
- paid services by default
- a native iOS app (the PWA is the app)
- virtual try-on

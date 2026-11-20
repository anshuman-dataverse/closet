-- Closet: initial schema (SPEC.md section 3).
-- Conventions: money in integer cents (USD); worn/bought days are `date` in the
-- user's time zone; every other time is timestamptz; every table has user_id + RLS.

create extension if not exists vector with schema extensions;
create extension if not exists pgcrypto with schema extensions;

-- ---------------------------------------------------------------- enums
create type public.occasion as enum ('office', 'college', 'party', 'home');
create type public.item_category as enum ('Tops', 'Bottoms', 'Layers', 'Shoes', 'Accessories', 'Sets & suits');
create type public.item_status as enum ('active', 'laundry', 'retired');
create type public.job_status as enum ('queued', 'running', 'done', 'failed');

-- ---------------------------------------------------------------- helpers
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------- profiles
create table public.profiles (
  user_id uuid primary key default auth.uid() references auth.users on delete cascade,
  sizes jsonb not null default '{}'::jsonb,                 -- {top, waist, inseam, shoe} US
  fit_pref text not null default '' check (fit_pref in ('slim', 'regular', 'relaxed', '')),
  monthly_budget_cents integer not null default 15000 check (monthly_budget_cents >= 0),
  paid_monthly_cap_cents integer not null default 0 check (paid_monthly_cap_cents >= 0),
  favorite_stores text[] not null default '{}',
  city_name text,
  latitude double precision,
  longitude double precision,
  timezone text not null default 'America/New_York',
  temp_unit text not null default 'F' check (temp_unit in ('F', 'C')),
  analysis jsonb,
  analyzed_at timestamptz,
  undertone_override text,
  contrast_override text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Every new auth user gets a profile row.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (user_id) values (new.id) on conflict do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------- items
create table public.items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  name text not null check (char_length(name) between 1 and 80),
  category public.item_category,
  type text,
  color_name text,
  color_hex text check (color_hex ~ '^#[0-9a-f]{6}$'),
  secondary_color text,
  pattern text,
  formality smallint check (formality between 1 and 5),
  warmth text check (warmth in ('light', 'medium', 'warm')),
  occasions public.occasion[] not null default '{}',
  brand text,
  size text,
  price_cents integer check (price_cents >= 0),
  bought_on date,
  store text,
  notes text,
  photo_path text,
  thumb_path text,
  cutout_path text,
  suggestions jsonb,
  tags_status text not null default 'none'
    check (tags_status in ('none', 'pending', 'ready', 'unsure', 'not_clothing', 'failed')),
  status public.item_status not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index items_user_idx on public.items (user_id, created_at desc);

-- 512 = FashionCLIP. Change if the eval picks another model (5.1).
create table public.item_embeddings (
  item_id uuid primary key references public.items on delete cascade,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  model text not null,
  embedding extensions.vector(512) not null,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------- outfits
create table public.outfits (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  name text,
  occasions public.occasion[] not null default '{}',
  source text not null default 'manual' check (source in ('manual', 'suggested')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.outfit_items (
  outfit_id uuid not null references public.outfits on delete cascade,
  item_id uuid not null references public.items on delete cascade,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  position smallint not null default 0,
  primary key (outfit_id, item_id)
);
create index outfit_items_item_idx on public.outfit_items (item_id);

-- ---------------------------------------------------------------- wear log
create table public.wear_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  worn_on date not null,
  occasion public.occasion not null,
  outfit_id uuid references public.outfits on delete set null,
  created_at timestamptz not null default now()
);
create unique index wear_logs_once_per_day
  on public.wear_logs (user_id, worn_on, outfit_id) where outfit_id is not null;
create index wear_logs_user_day_idx on public.wear_logs (user_id, worn_on desc);

-- Snapshot of what was worn, so stats survive outfit edits.
create table public.wear_log_items (
  wear_log_id uuid not null references public.wear_logs on delete cascade,
  item_id uuid not null references public.items on delete cascade,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  primary key (wear_log_id, item_id)
);
create index wear_log_items_item_idx on public.wear_log_items (item_id);

-- ---------------------------------------------------------------- wishlist
create table public.wishlist_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  name text not null check (char_length(name) between 1 and 120),
  category public.item_category,
  color_name text,
  occasion public.occasion,
  price_cents integer check (price_cents >= 0),
  url text check (url is null or url ~* '^https?://'),
  store text,
  notes text,
  photo_path text,
  image_url text check (image_url is null or image_url ~* '^https?://'),
  embedding extensions.vector(512),
  status text not null default 'wanted' check (status in ('wanted', 'bought', 'removed')),
  check_result jsonb,          -- SPEC calls this `check`; renamed because CHECK is a reserved word
  checked_at timestamptz,
  watch boolean not null default false,
  target_price_cents integer check (target_price_cents >= 0),
  last_seen_price_cents integer,
  last_price_check_at timestamptz,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------- hunts
create table public.hunts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  query text not null check (char_length(query) between 1 and 200),
  occasion public.occasion,
  budget_min_cents integer check (budget_min_cents >= 0),
  budget_max_cents integer check (budget_max_cents >= 0),
  notes text,
  use_gpt boolean not null default false,
  provider text not null default 'free' check (provider in ('free', 'gpt')),
  status public.job_status not null default 'queued',
  summary text,
  error text,
  pages_checked integer not null default 0,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);

create table public.hunt_results (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  hunt_id uuid not null references public.hunts on delete cascade,
  rank smallint not null,
  title text not null,
  store text,
  url text not null check (url ~* '^https?://'),
  image_url text check (image_url is null or image_url ~* '^https?://'),
  price_cents integer,
  was_price_cents integer,
  rating numeric(3, 2),
  rating_count integer,
  why text,
  quality text,
  size_available text not null default 'unknown' check (size_available in ('yes', 'no', 'unknown')),
  checked_at timestamptz not null default now()
);
create index hunt_results_hunt_idx on public.hunt_results (hunt_id, rank);

-- ---------------------------------------------------------------- style photos
create table public.style_photos (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  photo_path text not null,
  kind text not null check (kind in ('front', 'side', 'back', 'face', 'other')),
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------- job queue
create table public.jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  kind text not null check (kind in (
    'ping', 'tag_item', 'embed_wish', 'analyze_profile', 'suggest_outfits', 'check_wish',
    'find_gaps', 'run_hunt', 'price_check', 'train_ranker', 'backup'
  )),
  payload jsonb not null default '{}'::jsonb,
  status public.job_status not null default 'queued',
  result jsonb,
  error text,
  attempts smallint not null default 0,
  priority smallint not null default 0,      -- higher runs first
  worker_id text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);
create index jobs_queue_idx on public.jobs (status, priority desc, created_at);
create index jobs_user_idx on public.jobs (user_id, created_at desc);

create table public.workers (
  id text primary key,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  last_seen_at timestamptz not null default now(),
  version text,
  capabilities jsonb not null default '{}'::jsonb   -- {searxng, ollama, openai}
);

-- ---------------------------------------------------------------- learning
create table public.suggestion_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  occasion public.occasion not null,
  item_ids uuid[] not null,
  context jsonb not null default '{}'::jsonb,       -- weather, note
  score double precision,
  model_version text,
  action text not null check (action in ('shown', 'worn', 'saved', 'skipped', 'liked', 'disliked')),
  created_at timestamptz not null default now()
);
create index suggestion_events_user_idx on public.suggestion_events (user_id, created_at);

create table public.model_versions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  kind text not null check (kind in ('ranker', 'compat')),
  sample_count integer not null default 0,
  metrics jsonb not null default '{}'::jsonb,
  artifact_path text,
  active boolean not null default false,
  trained_at timestamptz not null default now()
);
create unique index model_versions_one_active
  on public.model_versions (user_id, kind) where active;

-- ---------------------------------------------------------------- shopping + paid usage
create table public.price_checks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  wishlist_id uuid not null references public.wishlist_items on delete cascade,
  checked_at timestamptz not null default now(),
  price_cents integer,
  in_stock boolean,
  source text check (source in ('jsonld', 'opengraph', 'gpt')),
  note text
);
create index price_checks_wish_idx on public.price_checks (wishlist_id, checked_at desc);

create table public.paid_usage (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  feature text not null,
  model text,
  input_tokens integer not null default 0,
  output_tokens integer not null default 0,
  web_search_calls integer not null default 0,
  est_cost_usd numeric(10, 4) not null default 0,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------- updated_at triggers
create trigger profiles_updated_at before update on public.profiles
  for each row execute function public.set_updated_at();
create trigger items_updated_at before update on public.items
  for each row execute function public.set_updated_at();
create trigger outfits_updated_at before update on public.outfits
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------- RLS
-- Default: the owner may select/insert/update/delete only their own rows.
do $$
declare
  t text;
begin
  foreach t in array array[
    'profiles', 'items', 'item_embeddings', 'outfits', 'outfit_items', 'wear_logs',
    'wear_log_items', 'wishlist_items', 'hunts', 'hunt_results', 'style_photos',
    'suggestion_events', 'model_versions', 'price_checks', 'paid_usage'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format(
      'create policy owner_all on public.%I for all to authenticated
         using (user_id = (select auth.uid()))
         with check (user_id = (select auth.uid()))', t);
  end loop;
end;
$$;

-- jobs: the owner can read their jobs, queue new ones, and delete queued ones.
-- Only the worker (service role) claims, runs and finishes jobs.
alter table public.jobs enable row level security;
create policy owner_select on public.jobs for select to authenticated
  using (user_id = (select auth.uid()));
create policy owner_enqueue on public.jobs for insert to authenticated
  with check (
    user_id = (select auth.uid())
    and status = 'queued' and attempts = 0 and worker_id is null
    and result is null and error is null and started_at is null and finished_at is null
  );
create policy owner_cancel on public.jobs for delete to authenticated
  using (user_id = (select auth.uid()) and status = 'queued');

-- workers: read-only to the owner (drives the "Mac offline" pill).
alter table public.workers enable row level security;
create policy owner_select on public.workers for select to authenticated
  using (user_id = (select auth.uid()));

-- Nothing in this app is meant for signed-out visitors.
revoke all on all tables in schema public from anon;
revoke all on all sequences in schema public from anon;

-- ---------------------------------------------------------------- queue functions (service role only)
create or replace function public.claim_job(p_worker text, p_user uuid default null)
returns setof public.jobs
language plpgsql
security definer
set search_path = ''
as $$
begin
  return query
  update public.jobs j
     set status = 'running',
         worker_id = p_worker,
         started_at = now(),
         attempts = j.attempts + 1,
         error = null
   where j.id = (
     select q.id
       from public.jobs q
      where q.status = 'queued'
        and (p_user is null or q.user_id = p_user)
      order by q.priority desc, q.created_at
      limit 1
      for update skip locked
   )
  returning j.*;
end;
$$;

create or replace function public.requeue_stale_jobs()
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  n integer;
begin
  with stale as (
    select id, attempts
      from public.jobs
     where status = 'running'
       and started_at < now() - interval '10 minutes'
     for update skip locked
  )
  update public.jobs j
     set status = case when s.attempts < 3 then 'queued'::public.job_status else 'failed'::public.job_status end,
         worker_id = null,
         error = case when s.attempts < 3 then j.error else 'Timed out after 3 attempts' end,
         finished_at = case when s.attempts < 3 then null else now() end
    from stale s
   where j.id = s.id;
  get diagnostics n = row_count;
  return n;
end;
$$;

revoke all on function public.claim_job(text, uuid) from public, anon, authenticated;
revoke all on function public.requeue_stale_jobs() from public, anon, authenticated;
grant execute on function public.claim_job(text, uuid) to service_role;
grant execute on function public.requeue_stale_jobs() to service_role;
revoke all on function public.handle_new_user() from public, anon, authenticated;

-- ---------------------------------------------------------------- views (security_invoker so RLS applies)
create view public.item_stats with (security_invoker = true) as
select
  i.id as item_id,
  i.user_id,
  count(wl.id)::integer as wear_count,
  max(wl.worn_on) as last_worn_on,
  case when i.price_cents is null then null
       else round(i.price_cents::numeric / greatest(1, count(wl.id)))::integer
  end as cost_per_wear_cents
from public.items i
left join public.wear_log_items wli on wli.item_id = i.id
left join public.wear_logs wl on wl.id = wli.wear_log_id
group by i.id;

create view public.outfit_stats with (security_invoker = true) as
select
  o.id as outfit_id,
  o.user_id,
  count(wl.id)::integer as wear_count,
  max(wl.worn_on) as last_worn_on
from public.outfits o
left join public.wear_logs wl on wl.outfit_id = o.id
group by o.id;

create view public.monthly_spend with (security_invoker = true) as
select
  i.user_id,
  date_trunc('month', i.bought_on)::date as month,
  i.category,
  sum(i.price_cents)::integer as total_cents,
  count(*)::integer as item_count
from public.items i
where i.bought_on is not null and i.price_cents is not null
group by i.user_id, date_trunc('month', i.bought_on), i.category;

revoke all on public.item_stats, public.outfit_stats, public.monthly_spend from anon;

-- ---------------------------------------------------------------- storage
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('wardrobe', 'wardrobe', false, 10485760, array['image/jpeg', 'image/webp', 'image/png'])
on conflict (id) do nothing;

create policy wardrobe_owner_select on storage.objects for select to authenticated
  using (bucket_id = 'wardrobe' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy wardrobe_owner_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'wardrobe' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy wardrobe_owner_update on storage.objects for update to authenticated
  using (bucket_id = 'wardrobe' and (storage.foldername(name))[1] = (select auth.uid())::text)
  with check (bucket_id = 'wardrobe' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy wardrobe_owner_delete on storage.objects for delete to authenticated
  using (bucket_id = 'wardrobe' and (storage.foldername(name))[1] = (select auth.uid())::text);

-- ---------------------------------------------------------------- realtime
alter publication supabase_realtime add table public.jobs, public.workers, public.hunts, public.hunt_results;

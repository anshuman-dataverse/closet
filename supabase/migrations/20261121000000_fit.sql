-- Fit per piece (slim, regular, oversized, flare, wide…) and which fit lists to show.
-- Fit ids live in worker/closet_worker/vocab/fits.yaml (exported to web/lib/domain/fits.json),
-- so new ones don't need a migration; the check keeps the column to plain short ids.

alter table public.items
  add column fit text check (fit ~ '^[a-z][a-z-]{1,19}$');

-- "Clothes I mostly wear": only decides which fit choices appear. Null shows every choice.
alter table public.profiles
  add column wears text check (wears in ('menswear', 'womenswear', 'both'));

-- Optional photo of the piece's own label (brand, size, material, sometimes fit).
alter table public.items
  add column label_path text;

-- Height, for length and proportion notes in the style profile (optional).
alter table public.profiles
  add column height_cm smallint check (height_cm between 100 and 250);

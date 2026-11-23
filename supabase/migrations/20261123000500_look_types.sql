-- Shop a look: the piece type per slot ({"Tops": "knit polo", ...}). Set by the app when you pick
-- types; the worker writes back the types it used, so Run again can show and change them.
alter table public.hunts
  add column look_types jsonb check (look_types is null or jsonb_typeof(look_types) = 'object');

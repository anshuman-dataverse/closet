-- Shop a look: one hunt that plans a whole outfit (top, layer, bottom, shoes, belt) and shops it.
alter table public.hunts
  add column kind text not null default 'item' check (kind in ('item', 'look')),
  add column look_mode text check (look_mode in ('own', 'new'));

-- Picks of a look: which slot they fill and which complete set they belong to (null: found, but
-- no complete set within budget used it). Pieces you own are listed with owned_item_id.
alter table public.hunt_results
  add column slot text,
  add column set_no smallint,
  add column owned_item_id uuid references public.items on delete set null;
alter table public.hunt_results alter column url drop not null;
alter table public.hunt_results add constraint hunt_results_url_or_owned
  check (url is not null or owned_item_id is not null);

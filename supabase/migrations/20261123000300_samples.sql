-- Sample pieces (added from Settings so ideas and looks have something to work with). Shown with a
-- "Sample" badge, left out of spend, removable in one tap.
alter table public.items add column is_sample boolean not null default false;

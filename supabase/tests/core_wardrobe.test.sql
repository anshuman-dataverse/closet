-- Run with: supabase test db
begin;
create extension if not exists pgtap with schema extensions;
select plan(14);

insert into auth.users (id, email, instance_id, aud, role) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'a@x.test', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated'),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'b@x.test', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated');

-- B owns one item (used to check A can't reference it).
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"bbbbbbbb-0000-0000-0000-000000000002","role":"authenticated"}', true);
insert into public.items (id, name, category) values ('bbbbbbbb-1111-0000-0000-000000000001', 'B shirt', 'Tops');
insert into public.wear_logs (worn_on, occasion) values ('2026-11-01', 'home');

-- A
select set_config('request.jwt.claims', '{"sub":"aaaaaaaa-0000-0000-0000-000000000001","role":"authenticated"}', true);
insert into public.items (id, name, category) values
  ('aaaaaaaa-1111-0000-0000-000000000001', 'Grey chinos', 'Bottoms'),
  ('aaaaaaaa-1111-0000-0000-000000000002', 'Navy oxford', 'Tops'),
  ('aaaaaaaa-1111-0000-0000-000000000003', 'Loafers', 'Shoes');

select throws_ok(
  $$ select public.save_outfit(null, '', '{office}', '{aaaaaaaa-1111-0000-0000-000000000001}') $$,
  '22023', 'Pick at least two pieces, like a top and a bottom.', 'outfits need two pieces');
select throws_ok(
  $$ select public.save_outfit(null, '', '{}', '{aaaaaaaa-1111-0000-0000-000000000001,aaaaaaaa-1111-0000-0000-000000000002}') $$,
  '22023', 'Choose at least one occasion.', 'outfits need an occasion');
select throws_ok(
  $$ select public.save_outfit(null, '', '{office}', '{aaaaaaaa-1111-0000-0000-000000000001,bbbbbbbb-1111-0000-0000-000000000001}') $$,
  '22023', null, 'another user''s piece is rejected');

create temp table t (id uuid) on commit drop;
grant all on t to authenticated;
insert into t select public.save_outfit(null, '  ', '{office,office}',
  '{aaaaaaaa-1111-0000-0000-000000000001,aaaaaaaa-1111-0000-0000-000000000002}');
select is((select name from public.outfits where id = (select id from t)), null, 'blank name is stored as null');
select is((select occasions::text from public.outfits where id = (select id from t)), '{office}', 'occasions deduplicated');
select is(
  (select array_agg(item_id order by position)::text from public.outfit_items where outfit_id = (select id from t)),
  '{aaaaaaaa-1111-0000-0000-000000000002,aaaaaaaa-1111-0000-0000-000000000001}',
  'pieces ordered by category (Tops before Bottoms)');

-- wear log + duplicate guard
select is((public.log_wear('2026-11-20', 'office', (select id from t),
  '{aaaaaaaa-1111-0000-0000-000000000001,aaaaaaaa-1111-0000-0000-000000000002}'))->>'status', 'logged', 'first wear logs');
select is((public.log_wear('2026-11-20', 'office', (select id from t),
  '{aaaaaaaa-1111-0000-0000-000000000001,aaaaaaaa-1111-0000-0000-000000000002}'))->>'status', 'already', 'same outfit, same day: already');
select is((select count(*)::int from public.wear_logs), 1, 'duplicate wrote nothing');
select is((public.log_wear('2026-11-20', 'home', null,
  '{aaaaaaaa-1111-0000-0000-000000000003}'))->>'status', 'logged', 'loose pieces (no outfit) can always log');

-- editing the outfit keeps the wear snapshot
select public.save_outfit((select id from t), 'Work', '{office}',
  '{aaaaaaaa-1111-0000-0000-000000000002,aaaaaaaa-1111-0000-0000-000000000003}');
select is((select count(*)::int from public.wear_log_items wli join public.wear_logs wl on wl.id = wli.wear_log_id
           where wl.outfit_id = (select id from t) and wli.item_id = 'aaaaaaaa-1111-0000-0000-000000000001'),
  1, 'snapshot survives an outfit edit');

-- delete all: only A's rows
update public.profiles set monthly_budget_cents = 99 where user_id = auth.uid();
select public.delete_all_my_data();
select is((select count(*)::int from public.items), 0, 'my items are gone');
select is((select monthly_budget_cents from public.profiles where user_id = auth.uid()), 15000, 'my profile is reset');
reset role;
select is((select count(*)::int from public.items where user_id = 'bbbbbbbb-0000-0000-0000-000000000002'), 1,
  'other users are untouched');

select * from finish();
rollback;

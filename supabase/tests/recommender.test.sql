begin;
create extension if not exists pgtap with schema extensions;
select plan(4);

insert into auth.users (id, email, instance_id, aud, role) values
  ('eeeeeeee-0000-0000-0000-000000000001', 'e@x.test', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated'),
  ('ffffffff-0000-0000-0000-000000000002', 'f@x.test', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated');

-- unit vectors along axis 1, a vector close to it, and one along axis 2
create temp table v as select
  ('[' || array_to_string(array[1] || array_fill(0, array[511]), ',') || ']')::extensions.vector(512) as x,
  ('[' || array_to_string(array[0.9, 0.1] || array_fill(0, array[510]), ',') || ']')::extensions.vector(512) as near,
  ('[' || array_to_string(array[0, 1] || array_fill(0, array[510]), ',') || ']')::extensions.vector(512) as y;

grant select on v to authenticated;  -- so the permission test below hits the function, not the temp table

insert into public.items (id, user_id, name, category) values
  ('eeeeeeee-1111-0000-0000-000000000001', 'eeeeeeee-0000-0000-0000-000000000001', 'Close', 'Tops'),
  ('eeeeeeee-1111-0000-0000-000000000002', 'eeeeeeee-0000-0000-0000-000000000001', 'Far', 'Tops'),
  ('eeeeeeee-1111-0000-0000-000000000003', 'eeeeeeee-0000-0000-0000-000000000001', 'Pants', 'Bottoms'),
  ('ffffffff-1111-0000-0000-000000000001', 'ffffffff-0000-0000-0000-000000000002', 'Theirs', 'Tops');
insert into public.item_embeddings (item_id, user_id, model, embedding) values
  ('eeeeeeee-1111-0000-0000-000000000001', 'eeeeeeee-0000-0000-0000-000000000001', 't', (select near from v)),
  ('eeeeeeee-1111-0000-0000-000000000002', 'eeeeeeee-0000-0000-0000-000000000001', 't', (select y from v)),
  ('eeeeeeee-1111-0000-0000-000000000003', 'eeeeeeee-0000-0000-0000-000000000001', 't', (select x from v)),
  ('ffffffff-1111-0000-0000-000000000001', 'ffffffff-0000-0000-0000-000000000002', 't', (select x from v));

select is(
  (select array_agg(item_id::text order by similarity desc) from public.nearest_items(
    'eeeeeeee-0000-0000-0000-000000000001', (select x from v), 'Tops', 5)),
  array['eeeeeeee-1111-0000-0000-000000000001', 'eeeeeeee-1111-0000-0000-000000000002'],
  'same category, owner only, most similar first');
select ok(
  (select similarity > 0.98 from public.nearest_items('eeeeeeee-0000-0000-0000-000000000001', (select x from v), 'Tops', 1)),
  'similarity is cosine');
select is((select count(*)::int from public.nearest_items('eeeeeeee-0000-0000-0000-000000000001', (select x from v), null, 5)),
  3, 'no category means all categories');

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"eeeeeeee-0000-0000-0000-000000000001","role":"authenticated"}', true);
select throws_ok(
  $$ select * from public.nearest_items('eeeeeeee-0000-0000-0000-000000000001', (select x from v), null, 5) $$,
  '42501', null, 'authenticated users cannot call it');

select * from finish();
rollback;

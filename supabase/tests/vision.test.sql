begin;
create extension if not exists pgtap with schema extensions;
select plan(3);

insert into auth.users (id, email, instance_id, aud, role) values
  ('cccccccc-0000-0000-0000-000000000001', 'c@x.test', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated'),
  ('dddddddd-0000-0000-0000-000000000002', 'd@x.test', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated');

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"dddddddd-0000-0000-0000-000000000002","role":"authenticated"}', true);
insert into public.items (id, name) values ('dddddddd-1111-0000-0000-000000000001', 'D shirt');

select set_config('request.jwt.claims', '{"sub":"cccccccc-0000-0000-0000-000000000001","role":"authenticated"}', true);
insert into public.items (id, name) values ('cccccccc-1111-0000-0000-000000000001', 'C shirt');
insert into public.jobs (kind, payload) values ('tag_item', '{"item_id":"cccccccc-1111-0000-0000-000000000001"}');
select is((select tags_status from public.items where id = 'cccccccc-1111-0000-0000-000000000001'), 'pending',
  'queuing tag_item marks the piece pending');

-- Queuing a job that names someone else's piece changes nothing.
insert into public.jobs (kind, payload) values ('tag_item', '{"item_id":"dddddddd-1111-0000-0000-000000000001"}');
reset role;
select is((select tags_status from public.items where id = 'dddddddd-1111-0000-0000-000000000001'), 'none',
  'another user''s piece is untouched');

insert into public.jobs (kind, payload, user_id) values ('ping', '{}', 'cccccccc-0000-0000-0000-000000000001');
select is((select count(*)::int from public.items where tags_status = 'pending'
           and user_id = 'cccccccc-0000-0000-0000-000000000001'), 1, 'other job kinds do nothing');

select * from finish();
rollback;

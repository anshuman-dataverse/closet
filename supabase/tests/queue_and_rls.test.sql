-- Run with: supabase test db
begin;
create extension if not exists pgtap with schema extensions;
select plan(12);

insert into auth.users (id, email, instance_id, aud, role) values
  ('11111111-1111-1111-1111-111111111111', 'a@x.test', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated'),
  ('22222222-2222-2222-2222-222222222222', 'b@x.test', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated');

select is((select count(*)::int from public.profiles), 2, 'a profile row is created per user');

-- user A
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);
insert into public.items (name) values ('Navy oxford shirt');
insert into public.jobs (kind) values ('ping');
select is((select count(*)::int from public.items), 1, 'owner sees own item');
select throws_ok($$ select public.claim_job('x') $$, '42501', null, 'authenticated cannot claim jobs');
select throws_ok($$ select public.requeue_stale_jobs() $$, '42501', null, 'authenticated cannot requeue jobs');
select throws_ok($$ insert into public.jobs (kind, status) values ('ping', 'running') $$, '42501', null, 'owner cannot insert a running job');

-- user B
select set_config('request.jwt.claims', '{"sub":"22222222-2222-2222-2222-222222222222","role":"authenticated"}', true);
select is((select count(*)::int from public.items), 0, 'other user sees no items');
select is((select count(*)::int from public.jobs), 0, 'other user sees no jobs');
select is((select count(*)::int from public.item_stats), 0, 'views respect RLS (security_invoker)');

-- worker (service role)
reset role;
select is((select attempts::int from public.claim_job('mac', '11111111-1111-1111-1111-111111111111')), 1, 'claim marks running and counts the attempt');
select is((select count(*)::int from public.claim_job('mac')), 0, 'a running job is not claimed twice');

update public.jobs set started_at = now() - interval '11 minutes';
select public.requeue_stale_jobs();
select is((select status::text from public.jobs), 'queued', 'stale job under 3 attempts goes back to queued');

update public.jobs set status = 'running', attempts = 3, started_at = now() - interval '11 minutes';
select public.requeue_stale_jobs();
select is((select status::text from public.jobs), 'failed', 'stale job after 3 attempts fails');

select * from finish();
rollback;

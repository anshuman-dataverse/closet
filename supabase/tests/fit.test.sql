begin;
select plan(7);

select has_column('public', 'items', 'fit', 'items.fit exists');
select has_column('public', 'profiles', 'wears', 'profiles.wears exists');
select has_column('public', 'items', 'label_path', 'items.label_path exists');

insert into auth.users (id, email) values ('00000000-0000-4000-8000-0000000000f1', 'fit@example.test');
set local role authenticated;
set local request.jwt.claims to '{"sub": "00000000-0000-4000-8000-0000000000f1", "role": "authenticated"}';

select lives_ok(
  $$insert into public.items (name, category, fit) values ('Flares', 'Bottoms', 'flare'), ('Dress', 'Sets & suits', 'a-line')$$,
  'fit ids are accepted'
);
select throws_ok(
  $$insert into public.items (name, category, fit) values ('Bad', 'Tops', 'Slim; drop table')$$,
  '23514', null, 'anything but a short id is refused'
);
select throws_ok(
  $$update public.profiles set wears = 'kids'$$,
  '23514', null, 'wears is one of three answers'
);

select lives_ok(
  $$insert into public.jobs (kind, payload) values ('read_label', '{"item_id": "x"}')$$,
  'the owner can queue read_label'
);

select * from finish();
rollback;

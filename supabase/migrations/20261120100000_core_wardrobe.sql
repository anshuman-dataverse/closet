-- Phase 1: atomic writes for the core wardrobe (SPEC 4.1–4.3, 4.6).

-- Display order for an outfit's pieces (SPEC 4.3).
create or replace function public.category_rank(c public.item_category)
returns smallint
language sql
immutable
set search_path = ''
as $$
  select case c
    when 'Tops' then 0 when 'Sets & suits' then 1 when 'Layers' then 2
    when 'Bottoms' then 3 when 'Shoes' then 4 when 'Accessories' then 5
    else 9 end::smallint;
$$;

-- Logs a wear and snapshots its pieces. The unique index on (user_id, worn_on, outfit_id)
-- is the duplicate guard: logging the same outfit twice on one day returns 'already'.
create or replace function public.log_wear(
  p_worn_on date,
  p_occasion public.occasion,
  p_outfit_id uuid,
  p_item_ids uuid[]
)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_ids uuid[] := array(select distinct x from unnest(p_item_ids) x where x is not null);
  v_id uuid;
begin
  if cardinality(v_ids) = 0 then
    raise exception 'Pick at least one piece.' using errcode = '22023';
  end if;
  if (select count(*) from public.items where id = any(v_ids)) <> cardinality(v_ids) then
    raise exception 'Some of those pieces aren’t in your closet.' using errcode = '22023';
  end if;

  insert into public.wear_logs (worn_on, occasion, outfit_id)
  values (p_worn_on, p_occasion, p_outfit_id)
  on conflict (user_id, worn_on, outfit_id) where outfit_id is not null do nothing
  returning id into v_id;

  if v_id is null then
    select id into v_id from public.wear_logs
     where user_id = auth.uid() and worn_on = p_worn_on and outfit_id = p_outfit_id;
    return jsonb_build_object('status', 'already', 'id', v_id);
  end if;

  insert into public.wear_log_items (wear_log_id, item_id)
  select v_id, x from unnest(v_ids) x;
  return jsonb_build_object('status', 'logged', 'id', v_id);
end;
$$;

-- Creates (p_id null) or updates an outfit and replaces its pieces, ordered by category.
create or replace function public.save_outfit(
  p_id uuid,
  p_name text,
  p_occasions public.occasion[],
  p_item_ids uuid[],
  p_source text default 'manual'
)
returns uuid
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_ids uuid[] := array(select distinct x from unnest(p_item_ids) x where x is not null);
  v_occ public.occasion[] := array(select distinct x from unnest(p_occasions) x where x is not null);
  v_name text := nullif(left(btrim(coalesce(p_name, '')), 80), '');
  v_id uuid;
begin
  if cardinality(v_ids) < 2 then
    raise exception 'Pick at least two pieces, like a top and a bottom.' using errcode = '22023';
  end if;
  if cardinality(v_occ) < 1 then
    raise exception 'Choose at least one occasion.' using errcode = '22023';
  end if;
  if (select count(*) from public.items where id = any(v_ids)) <> cardinality(v_ids) then
    raise exception 'Some of those pieces aren’t in your closet.' using errcode = '22023';
  end if;

  if p_id is null then
    insert into public.outfits (name, occasions, source)
    values (v_name, v_occ, coalesce(p_source, 'manual'))
    returning id into v_id;
  else
    update public.outfits set name = v_name, occasions = v_occ
     where id = p_id
    returning id into v_id;
    if v_id is null then
      raise exception 'That outfit no longer exists.' using errcode = 'P0002';
    end if;
    delete from public.outfit_items where outfit_id = v_id;
  end if;

  insert into public.outfit_items (outfit_id, item_id, position)
  select v_id, i.id,
         (row_number() over (order by public.category_rank(i.category), array_position(v_ids, i.id)) - 1)::smallint
    from public.items i
   where i.id = any(v_ids);
  return v_id;
end;
$$;

-- "Delete all my data" (SPEC 4.6, 9). The client removes Storage files first, then calls this.
-- security definer so it can also clear jobs and workers, which the owner can't delete through RLS.
-- Every statement is pinned to auth.uid().
create or replace function public.delete_all_my_data()
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
begin
  if v_uid is null then
    raise exception 'Sign in first.' using errcode = '42501';
  end if;
  delete from public.wear_logs where user_id = v_uid;
  delete from public.outfits where user_id = v_uid;
  delete from public.items where user_id = v_uid;            -- cascades embeddings, outfit_items, wear_log_items
  delete from public.wishlist_items where user_id = v_uid;   -- cascades price_checks
  delete from public.hunts where user_id = v_uid;            -- cascades hunt_results
  delete from public.style_photos where user_id = v_uid;
  delete from public.suggestion_events where user_id = v_uid;
  delete from public.model_versions where user_id = v_uid;
  delete from public.paid_usage where user_id = v_uid;
  delete from public.jobs where user_id = v_uid;
  delete from public.workers where user_id = v_uid;
  delete from public.profiles where user_id = v_uid;
  insert into public.profiles (user_id) values (v_uid);
end;
$$;

revoke all on function public.log_wear(date, public.occasion, uuid, uuid[]) from public, anon;
revoke all on function public.save_outfit(uuid, text, public.occasion[], uuid[], text) from public, anon;
revoke all on function public.delete_all_my_data() from public, anon;
grant execute on function public.log_wear(date, public.occasion, uuid, uuid[]) to authenticated;
grant execute on function public.save_outfit(uuid, text, public.occasion[], uuid[], text) to authenticated;
grant execute on function public.delete_all_my_data() to authenticated;

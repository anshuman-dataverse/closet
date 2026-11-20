-- Phase 3: near-duplicate search for "Do I need this?" (SPEC 5.6). Service role only.
create or replace function public.nearest_items(
  p_owner uuid,
  p_embedding extensions.vector(512),
  p_category public.item_category default null,
  p_k integer default 5
)
returns table (item_id uuid, similarity double precision)
language sql
stable
security definer
set search_path = ''
as $$
  select e.item_id, 1 - (e.embedding operator(extensions.<=>) p_embedding) as similarity
    from public.item_embeddings e
    join public.items i on i.id = e.item_id
   where e.user_id = p_owner
     and i.status <> 'retired'
     and (p_category is null or i.category = p_category)
   order by e.embedding operator(extensions.<=>) p_embedding
   limit greatest(1, least(p_k, 50));
$$;

revoke all on function public.nearest_items(uuid, extensions.vector, public.item_category, integer)
  from public, anon, authenticated;
grant execute on function public.nearest_items(uuid, extensions.vector, public.item_category, integer)
  to service_role;

-- Phase 2: queuing tag_item marks the piece as pending (SPEC 3, items.tags_status).
create or replace function public.mark_tagging_pending()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.kind = 'tag_item' and new.payload ? 'item_id' then
    update public.items
       set tags_status = 'pending'
     where id = (new.payload->>'item_id')::uuid
       and user_id = new.user_id;
  end if;
  return new;
end;
$$;

revoke all on function public.mark_tagging_pending() from public, anon, authenticated;

create trigger jobs_mark_tagging_pending
  after insert on public.jobs
  for each row execute function public.mark_tagging_pending();

-- New job kind: rate_outfit (Check my outfit).
alter table public.jobs drop constraint jobs_kind_check;
alter table public.jobs add constraint jobs_kind_check check (kind in (
  'ping', 'tag_item', 'read_label', 'embed_wish', 'analyze_profile', 'suggest_outfits',
  'rate_outfit', 'check_wish', 'find_gaps', 'run_hunt', 'price_check', 'train_ranker', 'backup'
));

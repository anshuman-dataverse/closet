-- New job kind: read_label (the Mac reads a piece's label photo).
alter table public.jobs drop constraint jobs_kind_check;
alter table public.jobs add constraint jobs_kind_check check (kind in (
  'ping', 'tag_item', 'read_label', 'embed_wish', 'analyze_profile', 'suggest_outfits',
  'check_wish', 'find_gaps', 'run_hunt', 'price_check', 'train_ranker', 'backup'
));

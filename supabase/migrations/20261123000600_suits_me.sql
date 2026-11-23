-- Would it suit me? A link or screenshot is checked as a wishlist row with status 'considering'
-- (hidden from the wishlist until you add it). New job kind: suits_me.
alter table public.wishlist_items drop constraint wishlist_items_status_check;
alter table public.wishlist_items add constraint wishlist_items_status_check
  check (status in ('considering', 'wanted', 'bought', 'removed'));

alter table public.jobs drop constraint jobs_kind_check;
alter table public.jobs add constraint jobs_kind_check check (kind in (
  'ping', 'tag_item', 'read_label', 'embed_wish', 'analyze_profile', 'suggest_outfits',
  'rate_outfit', 'check_wish', 'suits_me', 'find_gaps', 'run_hunt', 'price_check', 'train_ranker',
  'backup'
));

-- Style profile: a manual depth setting, like undertone and contrast (null = from photos).
alter table public.profiles
  add column depth_override text check (depth_override in ('light', 'medium', 'deep'));

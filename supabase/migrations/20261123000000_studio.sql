-- Studio image: the cut-out piece centered on a clean background (made on the Mac). Its thumbnail
-- sits next to it as <name>_thumb.jpg. The original photo and cut-out are kept.
alter table public.items add column studio_path text;

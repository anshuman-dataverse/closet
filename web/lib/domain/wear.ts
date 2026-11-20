// Wear counts and last-worn dates (SPEC 8): pieces from the wear_log_items snapshot, outfits from wear_logs.
import type { WearLog } from "@/lib/closet/types";

export type WearStat = { count: number; last: string | null };
export type WearStats = { items: Map<string, WearStat>; outfits: Map<string, WearStat> };

const bump = (m: Map<string, WearStat>, id: string, day: string) => {
  const s = m.get(id) ?? { count: 0, last: null };
  s.count += 1;
  if (!s.last || day > s.last) s.last = day;
  m.set(id, s);
};

export function wearStats(logs: readonly WearLog[]): WearStats {
  const items = new Map<string, WearStat>();
  const outfits = new Map<string, WearStat>();
  for (const l of logs) {
    for (const id of new Set(l.itemIds)) bump(items, id, l.worn_on);
    if (l.outfit_id) bump(outfits, l.outfit_id, l.worn_on);
  }
  return { items, outfits };
}

export const NO_WEAR: WearStat = { count: 0, last: null };

/** Newest first: by day, then by when it was logged. */
export const sortLogsNewest = (logs: readonly WearLog[]): WearLog[] =>
  [...logs].sort((a, b) => b.worn_on.localeCompare(a.worn_on) || b.created_at.localeCompare(a.created_at));

/** price / max(1, wears), in cents; null without a price. */
export const costPerWear = (priceCents: number | null | undefined, wears: number): number | null =>
  priceCents == null ? null : Math.round(priceCents / Math.max(1, wears));

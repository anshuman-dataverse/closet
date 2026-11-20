// Today's pick (SPEC 4.1): saved outfits for the occasion, leaving out any with a retired or
// in-laundry piece. Never-worn first, then the longest since worn; ties by created_at (oldest first).
import type { Item, Outfit } from "@/lib/closet/types";
import type { Occasion } from "@/lib/occasions";
import { NO_WEAR, type WearStats } from "./wear";

export function rotationFor(
  occasion: Occasion,
  outfits: readonly Outfit[],
  byId: ReadonlyMap<string, Item>,
  stats: WearStats,
): Outfit[] {
  return outfits
    .filter((o) => o.occasions.includes(occasion))
    .filter((o) => {
      const pieces = o.itemIds.map((id) => byId.get(id));
      return pieces.length > 0 && pieces.every((p) => p && p.status === "active");
    })
    .sort((a, b) => {
      const la = (stats.outfits.get(a.id) ?? NO_WEAR).last;
      const lb = (stats.outfits.get(b.id) ?? NO_WEAR).last;
      if (la !== lb) {
        if (la === null) return -1;
        if (lb === null) return 1;
        return la.localeCompare(lb);
      }
      return a.created_at.localeCompare(b.created_at);
    });
}

/** Outfits page order: least recently worn first (never worn first), newest created breaks ties. */
export function leastRecentlyWorn(outfits: readonly Outfit[], stats: WearStats): Outfit[] {
  return [...outfits].sort((a, b) => {
    const la = (stats.outfits.get(a.id) ?? NO_WEAR).last ?? "";
    const lb = (stats.outfits.get(b.id) ?? NO_WEAR).last ?? "";
    return la.localeCompare(lb) || b.created_at.localeCompare(a.created_at);
  });
}

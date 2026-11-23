// Deal hunts and price watch rules (SPEC 4.4, 5.8, 5.9). Pure functions, tested.
import type { Wish } from "@/lib/closet/types";
import type { Database } from "@/lib/database.types";

type T = Database["public"]["Tables"];
export type HuntRow = T["hunts"]["Row"];
export type HuntResult = T["hunt_results"]["Row"];
export type Hunt = HuntRow & { results: HuntResult[] };

/** Budget fields: reversed ones are swapped; blanks stay open. */
export function normalizeBudget(min: number | null, max: number | null): { min: number | null; max: number | null } {
  if (min != null && max != null && min > max) return { min: max, max: min };
  return { min, max };
}

/** The card's status line. */
export function huntStatus(h: Hunt, macOffline: boolean): string {
  if (h.status === "failed") return h.error ? `Failed: ${h.error}` : "Failed";
  if (h.status === "running") return "Searching…";
  if (h.status === "queued") return macOffline ? "Waiting for your Mac" : "Queued";
  const n = h.results.length;
  return n === 1 ? "1 pick" : `${n} picks`;
}

export function percentOff(price: number | null, was: number | null): number | null {
  if (price == null || was == null || was <= price) return null;
  const pct = Math.round((1 - price / was) * 100);
  return pct >= 1 ? pct : null;
}

export function sizeNote(s: HuntResult["size_available"]): string {
  if (s === "yes") return "Your size is in stock";
  if (s === "no") return "Your size is sold out";
  return "Size: check the store";
}

/**
 * A watched wish whose last checked price reached your target, or fell at least 15% below the
 * price you saved it at. Only real checked prices count; no check, no drop.
 */
export function priceDrop(w: Wish): { from: number | null; to: number } | null {
  const now = w.last_seen_price_cents;
  if (!w.watch || now == null || w.status !== "wanted") return null;
  const target = w.target_price_cents != null && now <= w.target_price_cents;
  const fell = w.price_cents != null && w.price_cents > 0 && now <= w.price_cents * 0.85;
  return target || fell ? { from: w.price_cents, to: now } : null;
}

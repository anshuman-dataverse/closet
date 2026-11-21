// Fit choices per category (SPEC 4.2 addition). The list comes from the worker's vocab/fits.yaml
// via fits.json, so the Mac's fit check and the buttons here always use the same ids.
import type { Category } from "@/lib/closet/types";
import data from "./fits.json";

export type Wears = "menswear" | "womenswear" | "both";
export type FitOption = { id: string; label: string };

type Raw = { groups: Record<string, { categories: string[]; fits: { id: string; label: string; wears: string[] }[] }> };
const GROUPS = Object.values((data as Raw).groups);

export const WEARS: readonly { id: Wears; label: string }[] = [
  { id: "menswear", label: "Menswear" },
  { id: "womenswear", label: "Womenswear" },
  { id: "both", label: "Both" },
];

export const isWears = (v: unknown): v is Wears => v === "menswear" || v === "womenswear" || v === "both";

/** Fit choices for a category. No answer yet (or "Both") shows every choice. Shoes and accessories: none. */
export function fitOptions(category: Category | null | undefined, wears: string | null | undefined): FitOption[] {
  const g = GROUPS.find((x) => category && x.categories.includes(category));
  if (!g) return [];
  const w = wears === "menswear" || wears === "womenswear" ? wears : null;
  return g.fits.filter((f) => !w || f.wears.includes(w)).map(({ id, label }) => ({ id, label }));
}

/** The label for a saved fit, even one your current answer would hide. Unknown ids show as-is. */
export function fitLabel(category: Category | null | undefined, id: string | null | undefined): string {
  if (!id) return "";
  return fitOptions(category, "both").find((f) => f.id === id)?.label ?? id;
}

/** A fit that still makes sense after the category changes, or "" if it doesn't. */
export function keepFit(category: Category, fit: string): string {
  return fitOptions(category, "both").some((f) => f.id === fit) ? fit : "";
}

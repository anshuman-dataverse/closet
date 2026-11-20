import type { Database } from "@/lib/database.types";

export type Occasion = Database["public"]["Enums"]["occasion"];

export const OCCASIONS: readonly { id: Occasion; label: string }[] = [
  { id: "office", label: "Office" },
  { id: "college", label: "College" },
  { id: "party", label: "Party" },
  { id: "home", label: "Home" },
];

export const isOccasion = (v: unknown): v is Occasion => OCCASIONS.some((o) => o.id === v);

/** Arrow-key movement inside the occasion radiogroup (wraps around). */
export function stepOccasion(current: Occasion, key: string): Occasion | null {
  const ids = OCCASIONS.map((o) => o.id);
  const i = Math.max(0, ids.indexOf(current));
  const n = ids.length;
  const at = (k: number): Occasion => ids[((k % n) + n) % n] ?? current;
  if (key === "ArrowDown" || key === "ArrowRight") return at(i + 1);
  if (key === "ArrowUp" || key === "ArrowLeft") return at(i - 1);
  if (key === "Home") return at(0);
  if (key === "End") return at(n - 1);
  return null;
}

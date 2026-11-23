// Shop a look: the piece types each occasion can use, per slot. The list comes from the worker's
// vocab/looks.yaml via looks.json, so the chips here and the Mac's plan always agree.
import data from "./looks.json";

export type LookSlot = { category: string; label: string; options: { id: string; label: string }[] };

const SLOT_LABEL: Record<string, string> = {
  Tops: "Top",
  Layers: "Layer",
  Bottoms: "Bottoms",
  Shoes: "Shoes",
  Accessories: "Belt",
};
const RAW = data as Record<string, Record<string, string[]>>;

const sentence = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

/** The slots for an occasion, each with its type choices (only slots with more than one choice). */
export function lookSlots(occasion: string): LookSlot[] {
  return Object.entries(RAW[occasion] ?? {})
    .filter(([, ts]) => ts.length > 1)
    .map(([category, ts]) => ({
      category,
      label: SLOT_LABEL[category] ?? category,
      options: ts.map((t) => ({ id: t, label: sentence(t) })),
    }));
}

/** Only picks that are real choices for the occasion; null when nothing is picked. */
export function cleanPicks(occasion: string, picks: Record<string, string>): Record<string, string> | null {
  const out: Record<string, string> = {};
  for (const [c, t] of Object.entries(picks)) if (RAW[occasion]?.[c]?.includes(t)) out[c] = t;
  return Object.keys(out).length ? out : null;
}

/** "Knit polo, blazer, chinos, loafers and belt" for a look card. */
export function lookTypesText(types: unknown): string {
  if (!types || typeof types !== "object" || Array.isArray(types)) return "";
  const order = Object.keys(SLOT_LABEL);
  const ts = Object.entries(types as Record<string, unknown>)
    .filter((e): e is [string, string] => typeof e[1] === "string")
    .sort(([a], [b]) => order.indexOf(a) - order.indexOf(b))
    .map(([, t]) => t);
  const last = ts.at(-1);
  if (last === undefined) return "";
  const s = ts.length === 1 ? last : `${ts.slice(0, -1).join(", ")} and ${last}`;
  return sentence(s);
}

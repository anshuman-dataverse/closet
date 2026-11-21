// What the Mac read from a piece's own label (worker read_label): brand, size, fit, materials.
// It only reports what's printed, and it fills only fields you left empty and haven't touched.
import type { Category } from "@/lib/closet/types";
import { fitLabel, keepFit } from "./fit";

export type LabelRead = { brand: string; size: string; fit: string; materials: string; notes: string[] };

const str = (v: unknown, n: number) => (typeof v === "string" ? v.trim().slice(0, n) : "");

export function parseLabel(raw: unknown): LabelRead | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const mats = Array.isArray(r.materials)
    ? r.materials
        .filter((m): m is { fiber: string; pct: number } => !!m && typeof m === "object" && "fiber" in m && "pct" in m)
        .map((m) => `${Number(m.pct)}% ${str(m.fiber, 30)}`)
        .join(", ")
    : "";
  return {
    brand: str(r.brand, 60),
    size: str(r.size, 20),
    fit: str(r.fit, 20),
    materials: mats,
    notes: Array.isArray(r.notes) ? r.notes.filter((n): n is string => typeof n === "string").slice(0, 4) : [],
  };
}

export type LabelForm = { category: Category; brand: string; size: string; fit: string; notes: string };
export type LabelKey = "brand" | "size" | "fit" | "notes";
const NAMES: Record<LabelKey, string> = { brand: "brand", size: "size", fit: "fit", notes: "materials" };

/** Fill empty, untouched fields from the label. Materials go into Notes only when Notes is empty. */
export function mergeLabel<F extends LabelForm>(
  form: F,
  touched: ReadonlySet<string>,
  l: LabelRead,
): { form: F; filled: LabelKey[] } {
  const next = { ...form };
  const filled: LabelKey[] = [];
  const offer: Record<LabelKey, string> = {
    brand: l.brand,
    size: l.size,
    fit: keepFit(form.category, l.fit),
    notes: l.materials,
  };
  for (const k of Object.keys(offer) as LabelKey[]) {
    if (!offer[k] || touched.has(k) || form[k].trim() !== "") continue;
    next[k] = offer[k] as F[LabelKey];
    filled.push(k);
  }
  return { form: next, filled };
}

const sentence = (n: string) => `${n[0]!.toUpperCase()}${n.slice(1)}.`;
const NO_TEXT = "Couldn’t find any text on the label. Take it straight on, close up, in good light.";

/** "Filled from the label: size and fit (Relaxed). Check them." plus anything it left out and why. */
export function labelMessage(l: LabelRead, filled: LabelKey[], category: Category): string {
  const why = l.notes.find((n) => !n.startsWith("no text found"));
  const tail = why ? ` ${sentence(why)}` : "";
  if (filled.length) {
    const parts = filled.map((k) => (k === "fit" ? `fit (${fitLabel(category, l.fit)})` : NAMES[k]));
    const list = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}` : parts[0];
    return `Filled from the label: ${list}. Check them.${tail}`;
  }
  if (l.brand || l.size || l.fit || l.materials) return `Read the label. Your own details were kept.${tail}`;
  return why ? sentence(why) : NO_TEXT;
}

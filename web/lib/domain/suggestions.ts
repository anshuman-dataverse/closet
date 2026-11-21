// The Mac's photo suggestions (SPEC 4.2, 5.1): parse them, merge them into the form without
// overwriting anything you've typed, and list what Apply would change on a saved piece.
import type { Category } from "@/lib/closet/types";
import { CATEGORIES } from "@/lib/closet/types";
import { isOccasion, type Occasion } from "@/lib/occasions";
import { fitLabel, keepFit } from "./fit";

export type TagStatus = "ready" | "unsure" | "not_clothing";

export type Suggestion = {
  name: string;
  category: Category;
  type: string;
  color_name: string;
  color_hex: string | null;
  pattern: string;
  formality: number | null;
  warmth: "light" | "medium" | "warm" | null;
  occasions: Occasion[];
  /** Only present when the Mac's fit check passed for this fit on your own photos. */
  fit: string;
  status: TagStatus;
};

const str = (v: unknown, n = 80) => (typeof v === "string" ? v.trim().slice(0, n) : "");

export function parseSuggestion(raw: unknown): Suggestion | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const status = (["ready", "unsure", "not_clothing"] as const).find((s) => s === r.status) ?? "ready";
  const category = CATEGORIES.find((c) => c === r.category);
  if (!category && status !== "not_clothing") return null;
  const hex = typeof r.color_hex === "string" && /^#[0-9a-f]{6}$/i.test(r.color_hex) ? r.color_hex.toLowerCase() : null;
  const f = Number(r.formality);
  const warmth = (["light", "medium", "warm"] as const).find((w) => w === r.warmth) ?? null;
  return {
    name: str(r.name),
    category: category ?? "Tops",
    type: str(r.type, 60),
    color_name: str(r.color_name, 40),
    color_hex: hex,
    pattern: str(r.pattern, 40),
    formality: Number.isInteger(f) && f >= 1 && f <= 5 ? f : null,
    warmth,
    occasions: Array.isArray(r.occasions) ? r.occasions.filter(isOccasion) : [],
    fit: typeof r.fit === "string" && category ? keepFit(category, r.fit) : "",
    status,
  };
}

/** The form fields suggestions can fill. Formality is a string because it comes from a <select>. */
export type SuggestableForm = {
  name: string;
  category: Category;
  type: string;
  color_name: string;
  pattern: string;
  occasions: Occasion[];
  formality: string;
  warmth: string;
  fit: string;
};
export type SuggestableKey = keyof SuggestableForm;
export const SUGGESTABLE: readonly SuggestableKey[] = [
  "name",
  "category",
  "type",
  "color_name",
  "pattern",
  "occasions",
  "formality",
  "warmth",
  "fit",
];

const asForm = (s: Suggestion): SuggestableForm => ({
  name: s.name,
  category: s.category,
  type: s.type ? s.type[0]!.toUpperCase() + s.type.slice(1) : "",
  color_name: s.color_name,
  pattern: s.pattern,
  occasions: s.occasions,
  formality: s.formality ? String(s.formality) : "",
  warmth: s.warmth ?? "",
  fit: s.fit,
});

/** Fill only the fields you haven't touched. Not-clothing suggestions change nothing. */
export function mergeSuggestions<F extends SuggestableForm>(
  form: F,
  touched: ReadonlySet<SuggestableKey>,
  s: Suggestion,
): { form: F; filled: SuggestableKey[] } {
  if (s.status === "not_clothing") return { form, filled: [] };
  const next = { ...form };
  const filled: SuggestableKey[] = [];
  const src = asForm(s);
  for (const k of SUGGESTABLE) {
    const v = src[k];
    const empty = Array.isArray(v) ? v.length === 0 : v === "";
    if (touched.has(k) || empty) continue;
    (next as SuggestableForm)[k] = v as never;
    filled.push(k);
  }
  // A suggested fit only stands if it belongs to the category the form ended up with.
  if (filled.includes("fit") && !keepFit(next.category, next.fit)) {
    next.fit = form.fit;
    filled.splice(filled.indexOf("fit"), 1);
  }
  return { form: next, filled };
}

/** Fields with a value count as touched when editing a saved piece: suggestions never overwrite them. */
export function touchedFromValues(form: SuggestableForm): Set<SuggestableKey> {
  return new Set(
    SUGGESTABLE.filter((k) => {
      const v = form[k];
      return Array.isArray(v) ? v.length > 0 : v !== "";
    }),
  );
}

export function statusMessage(status: TagStatus): string {
  if (status === "unsure") return "Not sure about this one. Check the type.";
  if (status === "not_clothing") return "That doesn’t look like clothing. Try another photo.";
  return "Filled in from your photo. Check the details.";
}

export const OFFLINE_MESSAGE = "Save it now, and the details will be suggested when your Mac is back.";

const LABEL: Record<SuggestableKey, string> = {
  name: "Name",
  category: "Category",
  type: "Type",
  color_name: "Color",
  pattern: "Pattern",
  occasions: "Good for",
  formality: "Formality",
  warmth: "Warmth",
  fit: "Fit",
};

export type SuggestionChange = { key: SuggestableKey; label: string; value: string; current: string; empty: boolean };

/** What Apply would change on a saved piece, for the review box. */
export function suggestionChanges(current: SuggestableForm, s: Suggestion): SuggestionChange[] {
  if (s.status === "not_clothing") return [];
  const src = asForm(s);
  const show = (k: SuggestableKey, v: SuggestableForm[SuggestableKey], c: SuggestableForm) =>
    Array.isArray(v) ? v.join(", ") : k === "fit" ? fitLabel(c.category, String(v)) : String(v);
  return SUGGESTABLE.flatMap((k) => {
    const v = show(k, src[k], src);
    const c = show(k, current[k], current);
    if (!v || v.toLowerCase() === c.toLowerCase()) return [];
    return [{ key: k, label: LABEL[k], value: v, current: c, empty: !c }];
  });
}

export function applyChanges<F extends SuggestableForm>(form: F, s: Suggestion, keys: readonly SuggestableKey[]): F {
  const next = { ...form };
  const src = asForm(s);
  for (const k of keys) (next as SuggestableForm)[k] = src[k] as never;
  return next;
}

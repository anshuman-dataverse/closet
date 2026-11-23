// Sample pieces for trying ideas, looks and What's missing before your own closet is in. Added
// from Settings, shown with a "Sample" badge, never counted as spend, removed in one tap.
import type { Category } from "@/lib/closet/types";
import type { Occasion } from "@/lib/occasions";
import { NAMED } from "./colors";

type Sample = {
  name: string;
  category: Category;
  type: string;
  color_name: string;
  formality: number;
  warmth: "light" | "medium" | "warm";
  occasions: Occasion[];
  fit: string | null;
};

const s = (
  name: string,
  category: Category,
  type: string,
  color_name: string,
  formality: number,
  warmth: Sample["warmth"],
  occasions: Occasion[],
  fit: string | null = null,
): Sample => ({ name, category, type, color_name, formality, warmth, occasions, fit });

export const SAMPLES: readonly Sample[] = [
  s("Light blue oxford shirt", "Tops", "oxford shirt", "light blue", 3, "light", ["office", "college"], "regular"),
  s("White oxford shirt", "Tops", "oxford shirt", "white", 3, "light", ["office", "college", "party"], "slim"),
  s("Navy polo shirt", "Tops", "polo shirt", "navy", 2, "light", ["college", "party"], "slim"),
  s("Grey t-shirt", "Tops", "t-shirt", "grey", 1, "light", ["home", "college"], "relaxed"),
  s("Burgundy henley", "Tops", "henley", "burgundy", 2, "light", ["college", "home"], "regular"),
  s(
    "Charcoal crew neck sweater",
    "Layers",
    "crew neck sweater",
    "charcoal",
    3,
    "warm",
    ["office", "college"],
    "regular",
  ),
  s("Navy blazer", "Layers", "blazer", "navy", 4, "medium", ["office", "party"], "slim"),
  s("Olive overshirt", "Layers", "overshirt", "olive", 2, "medium", ["college", "party"], "relaxed"),
  s("Grey hoodie", "Layers", "hoodie", "grey", 1, "medium", ["home", "college"], "oversized"),
  s("Navy chinos", "Bottoms", "chinos", "navy", 3, "medium", ["office", "college"], "slim"),
  s("Khaki chinos", "Bottoms", "chinos", "khaki", 3, "medium", ["office", "college", "party"], "straight"),
  s("Charcoal dress trousers", "Bottoms", "dress trousers", "charcoal", 4, "medium", ["office", "party"], "slim"),
  s("Dark wash jeans", "Bottoms", "dark wash jeans", "indigo", 2, "medium", ["college", "party"], "straight"),
  s("Grey joggers", "Bottoms", "joggers", "grey", 1, "medium", ["home"], "relaxed"),
  s("Brown loafers", "Shoes", "loafers", "brown", 4, "medium", ["office", "party"]),
  s("White sneakers", "Shoes", "white sneakers", "white", 2, "light", ["college", "home", "party"]),
  s("Brown chelsea boots", "Shoes", "chelsea boots", "brown", 3, "warm", ["office", "college", "party"]),
  s("Black derby shoes", "Shoes", "derby shoes", "black", 4, "medium", ["office"]),
  s("Brown belt", "Accessories", "belt", "brown", 3, "light", ["office", "college", "party"]),
  s("Silver watch", "Accessories", "watch", "silver", 3, "light", ["office", "party"]),
  s("Navy cap", "Accessories", "cap", "navy", 1, "light", ["college", "home"]),
];

/** Rows to insert: every key set, so a bulk insert can't leave anything null by accident. */
export function sampleRows() {
  return SAMPLES.map((x) => ({
    ...x,
    color_hex: NAMED[x.color_name] ?? null,
    status: "active" as const,
    is_sample: true,
    pattern: "solid",
  }));
}

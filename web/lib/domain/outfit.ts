import type { Category, Item, Outfit } from "@/lib/closet/types";

// Display order of an outfit's pieces (SPEC 4.3).
export const CATEGORY_ORDER: readonly Category[] = [
  "Tops",
  "Sets & suits",
  "Layers",
  "Bottoms",
  "Shoes",
  "Accessories",
];

export const categoryRank = (c: Category | null | undefined): number => {
  const k = c ? CATEGORY_ORDER.indexOf(c) : -1;
  return k < 0 ? 9 : k;
};

export const orderPieces = <T extends Pick<Item, "category">>(items: readonly T[]): T[] =>
  items
    .map((it, i) => ({ it, i }))
    .sort((a, b) => categoryRank(a.it.category) - categoryRank(b.it.category) || a.i - b.i)
    .map((x) => x.it);

/** The pieces of an outfit that still exist, in display order. */
export function outfitPieces(o: Pick<Outfit, "itemIds">, byId: ReadonlyMap<string, Item>): Item[] {
  return orderPieces(o.itemIds.map((id) => byId.get(id)).filter((x): x is Item => !!x));
}

/** The name, or the first two pieces joined with " + ". */
export function outfitName(o: Pick<Outfit, "name">, pieces: readonly Pick<Item, "name">[]): string {
  const n = (o.name ?? "").trim();
  if (n) return n;
  const auto = pieces
    .slice(0, 2)
    .map((p) => p.name)
    .join(" + ");
  return auto || "Untitled outfit";
}

export function validateOutfit(itemIds: readonly string[], occasions: readonly string[]): string | null {
  if (new Set(itemIds).size < 2) return "Pick at least two pieces, like a top and a bottom.";
  if (occasions.length < 1) return "Choose at least one occasion.";
  return null;
}

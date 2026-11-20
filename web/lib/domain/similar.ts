// Text-only "similar" check before embeddings exist (SPEC 8): same category and a meaningful
// shared word from the type or name, ignoring color and generic words. Color matches come first.
import type { Category } from "@/lib/closet/types";
import { colorKey, NAMED } from "@/lib/domain/colors";

const GENERIC = new Set([
  "slim",
  "regular",
  "relaxed",
  "fit",
  "classic",
  "cotton",
  "stretch",
  "casual",
  "formal",
  "long",
  "short",
  "sleeve",
  "men",
  "mens",
  "the",
  "and",
  "with",
  "for",
  "new",
]);
const COLOR_WORDS = new Set([...Object.keys(NAMED).flatMap((k) => k.split(" ")), "light", "dark"]);

export function meaningfulWords(s: string): Set<string> {
  return new Set(
    s
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter((w) => w.length > 2 && !GENERIC.has(w) && !COLOR_WORDS.has(w))
      .map((w) => (w.endsWith("s") && w.length > 4 && !w.endsWith("ss") ? w.slice(0, -1) : w)),
  );
}

type Thing = { name: string; type?: string | null; category: Category | null; color_name?: string | null };

export function similarTo<T extends Thing & { status?: string }>(x: Thing, owned: readonly T[]): T[] {
  if (!x.category) return [];
  const ws = meaningfulWords(`${x.name} ${x.type ?? ""}`);
  if (!ws.size) return [];
  const ck = colorKey(x.color_name ?? x.name);
  const hits = owned.filter((o) => {
    if (o.category !== x.category || o.status === "retired") return false;
    const ow = meaningfulWords(`${o.name} ${o.type ?? ""}`);
    return [...ws].some((w) => ow.has(w));
  });
  const sameColor = (o: T) => !!ck && colorKey(o.color_name ?? o.name) === ck;
  return [...hits.filter(sameColor), ...hits.filter((o) => !sameColor(o))];
}

export function overlapNote(hits: readonly { name: string }[]): string {
  if (!hits.length) return "";
  const names = hits
    .slice(0, 3)
    .map((h) => h.name)
    .join(", ");
  return hits.length === 1 ? `You own 1 similar: ${names}.` : `You own ${hits.length} similar: ${names}.`;
}

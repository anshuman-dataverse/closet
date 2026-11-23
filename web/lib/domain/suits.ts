// "Would it suit me?": the Mac's answer, stored in wishlist_items.check_result.suits.
import { parseRating, type Rating } from "@/components/RatingBox";

export type SuitsRead = {
  from: "link" | "screenshot";
  type: string;
  category: string;
  color: string | null;
  color_source: "you" | "store" | "picture" | "none";
  link_note: string | null;
};
export type Suits = Rating & { read: SuitsRead | null };

export function suitsOf(checkResult: unknown): Suits | null {
  if (!checkResult || typeof checkResult !== "object") return null;
  const raw = (checkResult as { suits?: unknown }).suits;
  const r = parseRating(raw);
  if (!r) return null;
  const read = (raw as { read?: SuitsRead }).read;
  return { ...r, read: read && typeof read.type === "string" ? read : null };
}

const SOURCE: Record<SuitsRead["color_source"], string> = {
  you: "the color you set",
  store: "the color the store states",
  picture: "read from the picture",
  none: "",
};

/** "Read from the store’s page: knit polo in navy (the color the store states)." */
export function readLine(r: SuitsRead | null): string {
  if (!r) return "";
  const where = r.from === "link" ? "Read from the store’s page" : "Read from your screenshot";
  const color = r.color ? ` in ${r.color}` : "";
  const src = r.color && SOURCE[r.color_source] ? ` (${SOURCE[r.color_source]})` : "";
  const note = r.link_note ? ` ${r.link_note}` : "";
  return `${where}: ${r.type}${color}${src}.${note}`;
}

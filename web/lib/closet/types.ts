import type { Database } from "@/lib/database.types";

type T = Database["public"]["Tables"];
export type Category = Database["public"]["Enums"]["item_category"];
export type ItemStatus = Database["public"]["Enums"]["item_status"];
export type Item = T["items"]["Row"];
export type Profile = T["profiles"]["Row"];
export type Outfit = T["outfits"]["Row"] & { itemIds: string[] };
export type WearLog = T["wear_logs"]["Row"] & { itemIds: string[] };

export const CATEGORIES: readonly Category[] = ["Tops", "Bottoms", "Layers", "Shoes", "Accessories", "Sets & suits"];

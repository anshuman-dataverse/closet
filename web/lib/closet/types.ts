import type { Database } from "@/lib/database.types";

type T = Database["public"]["Tables"];
export type Category = Database["public"]["Enums"]["item_category"];
export type ItemStatus = Database["public"]["Enums"]["item_status"];
export type Item = T["items"]["Row"];
export type Profile = T["profiles"]["Row"];
export type Outfit = T["outfits"]["Row"] & { itemIds: string[] };
export type WearLog = T["wear_logs"]["Row"] & { itemIds: string[] };

export const CATEGORIES: readonly Category[] = ["Tops", "Bottoms", "Layers", "Shoes", "Accessories", "Sets & suits"];

export type Wish = Omit<T["wishlist_items"]["Row"], "embedding">;
export const WISH_COLUMNS =
  "id,user_id,name,category,color_name,occasion,price_cents,url,store,notes,photo_path,image_url,status," +
  "check_result,checked_at,watch,target_price_cents,last_seen_price_cents,last_price_check_at,created_at";

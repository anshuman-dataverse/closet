// Test helpers for domain tests.
import type { Item, Outfit, WearLog } from "@/lib/closet/types";

let n = 0;
export function item(p: Partial<Item> & { id: string }): Item {
  return {
    user_id: "u",
    name: p.id,
    category: "Tops",
    type: null,
    color_name: null,
    color_hex: null,
    secondary_color: null,
    pattern: null,
    formality: null,
    warmth: null,
    occasions: [],
    brand: null,
    size: null,
    price_cents: null,
    bought_on: null,
    store: null,
    notes: null,
    photo_path: null,
    thumb_path: null,
    cutout_path: null,
    studio_path: null,
    is_sample: false,
    label_path: null,
    fit: null,
    suggestions: null,
    tags_status: "none",
    status: "active",
    created_at: `2026-01-01T00:00:${String(n++ % 60).padStart(2, "0")}Z`,
    updated_at: "2026-01-01T00:00:00Z",
    ...p,
  };
}
export function outfit(p: Partial<Outfit> & { id: string; itemIds: string[] }): Outfit {
  return {
    user_id: "u",
    name: null,
    occasions: ["office"],
    source: "manual",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...p,
  };
}
export function log(p: Partial<WearLog> & { worn_on: string; itemIds: string[] }): WearLog {
  return {
    id: `l${n++}`,
    user_id: "u",
    occasion: "office",
    outfit_id: null,
    created_at: `${p.worn_on}T12:00:00Z`,
    ...p,
  };
}

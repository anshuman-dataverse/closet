// Owner data helpers for e2e. Service role, local stack only.
import { admin } from "./admin";
import { OWNER } from "./env";

export const TZ = "America/New_York";
export const today = () => new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date());
export const daysAgo = (n: number) => new Date(Date.parse(today()) - n * 86_400_000).toISOString().slice(0, 10);

async function listFiles(prefix: string): Promise<string[]> {
  const out: string[] = [];
  const { data } = await admin.storage.from("wardrobe").list(prefix, { limit: 1000 });
  for (const e of data ?? []) {
    const p = `${prefix}/${e.name}`;
    if (e.id === null) out.push(...(await listFiles(p)));
    else out.push(p);
  }
  return out;
}
export const ownerFiles = () => listFiles(OWNER.id);

export async function resetOwnerData() {
  const files = await ownerFiles();
  if (files.length) await admin.storage.from("wardrobe").remove(files);
  for (const t of [
    "wear_logs",
    "outfits",
    "items",
    "jobs",
    "workers",
    "wishlist_items",
    "suggestion_events",
    "hunts",
    "style_photos",
    "model_versions",
    "paid_usage",
  ] as const) {
    await admin.from(t).delete().eq("user_id", OWNER.id);
  }
  await admin
    .from("profiles")
    .update({
      monthly_budget_cents: 15000,
      sizes: {},
      fit_pref: "",
      wears: null,
      favorite_stores: [],
      city_name: null,
      latitude: null,
      longitude: null,
      timezone: TZ,
      temp_unit: "F",
      paid_monthly_cap_cents: 0,
    })
    .eq("user_id", OWNER.id);
}

type SeedItem = {
  name: string;
  category: "Tops" | "Bottoms" | "Layers" | "Shoes" | "Accessories" | "Sets & suits";
  color_hex?: string;
  occasions?: ("office" | "college" | "party" | "home")[];
  price_cents?: number | null;
  bought_on?: string | null;
  status?: "active" | "laundry" | "retired";
};

export async function seedItems(list: SeedItem[]): Promise<Record<string, string>> {
  const rows = list.map((x, n) => ({
    user_id: OWNER.id,
    occasions: ["office"] as SeedItem["occasions"],
    created_at: new Date(Date.now() - (100 - n) * 1000).toISOString(),
    ...x,
    status: x.status ?? "active", // bulk inserts send null (not the default) for keys some rows lack
  }));
  const { data, error } = await admin.from("items").insert(rows).select("id,name");
  if (error) throw error;
  return Object.fromEntries(data.map((r) => [r.name, r.id]));
}

export async function seedOutfit(
  name: string,
  itemIds: string[],
  occasions: SeedItem["occasions"] = ["office"],
  createdMsAgo = 0,
) {
  const { data, error } = await admin
    .from("outfits")
    .insert({
      user_id: OWNER.id,
      name,
      occasions: occasions!,
      created_at: new Date(Date.now() - createdMsAgo).toISOString(),
    })
    .select("id")
    .single();
  if (error) throw error;
  await admin
    .from("outfit_items")
    .insert(itemIds.map((item_id, position) => ({ outfit_id: data.id, item_id, user_id: OWNER.id, position })));
  return data.id;
}

export async function seedWear(
  worn_on: string,
  outfit_id: string | null,
  itemIds: string[],
  occasion: "office" | "college" | "party" | "home" = "office",
) {
  const { data, error } = await admin
    .from("wear_logs")
    .insert({ user_id: OWNER.id, worn_on, outfit_id, occasion })
    .select("id")
    .single();
  if (error) throw error;
  await admin
    .from("wear_log_items")
    .insert(itemIds.map((item_id) => ({ wear_log_id: data.id, item_id, user_id: OWNER.id })));
  return data.id;
}

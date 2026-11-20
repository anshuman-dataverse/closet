// Loads the prototype's sample closet into the LOCAL stack for ALLOWED_EMAIL (from .env.local).
// No photos: pieces show their color swatch. Run: pnpm seed [--reset]
import { createClient } from "@supabase/supabase-js";
import { readFileSync } from "node:fs";

const env = Object.fromEntries(
  readFileSync(new URL("../.env.local", import.meta.url), "utf8")
    .split("\n")
    .map((l) => l.replace(/#.*/, "").trim())
    .filter(Boolean)
    .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]),
);
const url = env.NEXT_PUBLIC_SUPABASE_URL;
if (!/^http:\/\/(127\.0\.0\.1|localhost)/.test(url)) throw new Error("seed only runs against the local stack");
const LOCAL_SERVICE_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU";
const db = createClient(url, LOCAL_SERVICE_KEY, { auth: { persistSession: false } });

const { data: users } = await db.auth.admin.listUsers({ perPage: 1000 });
const user = users.users.find((u) => u.email === env.ALLOWED_EMAIL);
if (!user) throw new Error(`No local user ${env.ALLOWED_EMAIL}. Run pnpm dev:user first.`);
const uid = user.id;

if (process.argv.includes("--reset")) {
  for (const t of ["wear_logs", "outfits", "items"]) await db.from(t).delete().eq("user_id", uid);
}

const tz = "America/New_York";
const today = new Intl.DateTimeFormat("en-CA", { timeZone: tz }).format(new Date());
const day = (n) => new Date(Date.parse(today) - n * 86400000).toISOString().slice(0, 10);
const id = () => crypto.randomUUID();
const I = {};
const items = [
  [
    "i1",
    "Navy oxford shirt",
    "Tops",
    "Oxford shirt",
    "Navy",
    "#1f2a48",
    ["office", "college"],
    3950,
    6,
    3,
    "M",
    "Uniqlo",
  ],
  ["i2", "White oxford shirt", "Tops", "Oxford shirt", "White", "#f6f6f3", ["office", "party"], 3200, 70, 3],
  ["i3", "Grey chinos", "Bottoms", "Chinos", "Grey", "#8a8f98", ["office", "college"], 4800, 40, 3],
  ["i4", "Dark wash jeans", "Bottoms", "Jeans", "Indigo", "#27365a", ["college", "party", "home"], 6000, 200, 2],
  [
    "i5",
    "Charcoal merino sweater",
    "Layers",
    "Crew sweater",
    "Charcoal",
    "#3c3f47",
    ["office", "college"],
    5500,
    12,
    3,
  ],
  ["i6", "White sneakers", "Shoes", "Sneakers", "White", "#efefea", ["college", "home", "party"], 8000, 150, 2],
  ["i7", "Brown chelsea boots", "Shoes", "Chelsea boots", "Brown", "#6a4a33", ["office", "party"], 12000, 95, 4],
  ["i8", "Black bomber jacket", "Layers", "Bomber jacket", "Black", "#1c1c1e", ["party", "college"], 9000, 45, 2],
  ["i9", "Olive overshirt", "Layers", "Overshirt", "Olive", "#6a6a39", ["college", "home"], 4500, 20, 2],
  ["i10", "Grey joggers", "Bottoms", "Joggers", "Grey", "#8a8f98", ["home"], null, null, 1],
];
const rows = items.map(
  ([k, name, category, type, color_name, color_hex, occasions, price_cents, ago, formality, size, brand], n) => {
    I[k] = id();
    return {
      id: I[k],
      user_id: uid,
      name,
      category,
      type,
      color_name,
      color_hex,
      occasions,
      price_cents,
      bought_on: ago == null ? null : day(ago),
      formality,
      size: size ?? null,
      brand: brand ?? null,
      pattern: "solid",
      created_at: new Date(Date.now() - (20 - n) * 1000).toISOString(),
    };
  },
);
let r = await db.from("items").insert(rows);
if (r.error) throw r.error;

const O = {};
const outfits = [
  ["o1", "Classic office", ["i1", "i5", "i3", "i7"], ["office"]],
  ["o2", "Crisp and simple", ["i2", "i3", "i7"], ["office"]],
  ["o3", "Easy college", ["i9", "i4", "i6"], ["college"]],
  ["o4", "Night out", ["i8", "i2", "i4", "i7"], ["party"]],
];
r = await db.from("outfits").insert(
  outfits.map(([k, name, , occasions], n) => {
    O[k] = id();
    return {
      id: O[k],
      user_id: uid,
      name,
      occasions,
      created_at: new Date(Date.now() - (10 - n) * 1000).toISOString(),
    };
  }),
);
if (r.error) throw r.error;
r = await db
  .from("outfit_items")
  .insert(
    outfits.flatMap(([k, , ids]) => ids.map((x, p) => ({ outfit_id: O[k], item_id: I[x], user_id: uid, position: p }))),
  );
if (r.error) throw r.error;

const logs = [
  [1, "o2", "office"],
  [3, "o3", "college"],
  [5, "o1", "office"],
  [9, "o4", "party"],
  [12, "o3", "college"],
];
for (const [ago, o, occasion] of logs) {
  const lid = id();
  r = await db.from("wear_logs").insert({ id: lid, user_id: uid, worn_on: day(ago), occasion, outfit_id: O[o] });
  if (r.error) throw r.error;
  const ids = outfits.find((x) => x[0] === o)[2];
  r = await db.from("wear_log_items").insert(ids.map((x) => ({ wear_log_id: lid, item_id: I[x], user_id: uid })));
  if (r.error) throw r.error;
}
console.log(`seeded ${items.length} pieces, ${outfits.length} outfits, ${logs.length} wears for ${env.ALLOWED_EMAIL}`);

import type { ChildProcess } from "node:child_process";
import { admin } from "./admin";
import { resetOwnerData, seedItems } from "./data";
import { OWNER } from "./env";
import { expect, test } from "./fixtures";
import { waitForHeartbeat } from "./helpers-worker";
import { startFakeWorker, stopWorker } from "./worker-process";

let worker: ChildProcess | undefined;
test.beforeEach(resetOwnerData);
test.afterEach(async () => {
  await stopWorker(worker);
  worker = undefined;
});

const OFFICE = (name: string, category: "Tops" | "Bottoms" | "Shoes", color_hex: string) => ({
  name,
  category,
  color_hex,
  occasions: ["office" as const],
});

async function seedOffice() {
  return seedItems([
    OFFICE("Navy oxford", "Tops", "#1f2a48"),
    OFFICE("White oxford", "Tops", "#f6f6f3"),
    OFFICE("Light blue shirt", "Tops", "#a9c4e4"),
    OFFICE("Grey chinos", "Bottoms", "#8a8f98"),
    OFFICE("Khaki chinos", "Bottoms", "#b5a273"),
    OFFICE("Navy trousers", "Bottoms", "#27365a"),
    OFFICE("Brown boots", "Shoes", "#6a4a33"),
    OFFICE("Black loafers", "Shoes", "#1c1c1e"),
    OFFICE("Tan derbies", "Shoes", "#c19f72"),
  ]);
}

test("ideas: they load on their own, then save one, wear one, thumbs down one — every action is recorded", async ({
  page,
  signIn,
}) => {
  test.setTimeout(90_000);
  await seedOffice();
  worker = startFakeWorker();
  await waitForHeartbeat();
  await signIn();
  await page.getByRole("radio", { name: "office" }).click();
  // No saved outfits yet, so the Mac's ideas lead Today, and they arrive without asking.
  await expect(page.getByRole("heading", { name: "Office ideas from your closet" })).toBeVisible();
  const ideas = page.getByRole("region", { name: /ideas/ }); // "More ideas" once one is saved
  const cards = ideas.locator("article.combo");
  await expect(cards).toHaveCount(3, { timeout: 30_000 });
  // Coming back to Today doesn't ask again.
  await page.goto("/closet");
  await page.goto("/today");
  await expect(cards).toHaveCount(3);
  // A note asks again with it.
  await ideas.getByLabel(/Anything special today/).fill("client meeting at 2");
  await ideas.getByRole("button", { name: "New ideas" }).click();
  await expect(ideas.getByRole("status")).toHaveCount(0, { timeout: 30_000 });
  await expect(cards).toHaveCount(3);
  await expect(cards.first().locator("p")).toHaveText(/\.$/); // a reason sentence

  await cards.nth(0).getByRole("button", { name: "Save outfit" }).click();
  await expect(cards.nth(0).getByRole("button", { name: "Saved" })).toBeDisabled();
  await cards.nth(1).getByRole("button", { name: "Wear today" }).click();
  await expect(page.locator(".toast")).toContainText("Logged for today");
  await cards.nth(2).getByRole("button", { name: "Not for me" }).click();
  await expect(cards.nth(2).getByRole("button", { name: "Not for me" })).toHaveAttribute("aria-pressed", "true");

  const { data: events } = await admin.from("suggestion_events").select("action,context").eq("user_id", OWNER.id);
  const actions = (events ?? []).map((e) => e.action).sort();
  expect(actions).toEqual(["disliked", "saved", "shown", "shown", "shown", "shown", "shown", "shown", "worn"].sort());
  const note = (e: { context: unknown }) => (e.context as { note?: string }).note;
  expect((events ?? []).filter((e) => note(e) === "client meeting at 2")).toHaveLength(6); // 3 shown + 3 acted on
  expect((events ?? []).filter((e) => note(e) === "")).toHaveLength(3); // the first, automatic ideas
  const { data: outfits } = await admin.from("outfits").select("source").eq("user_id", OWNER.id);
  expect(outfits?.map((o) => o.source)).toEqual(["suggested", "suggested"]);
  const { count } = await admin.from("wear_logs").select("*", { count: "exact", head: true }).eq("user_id", OWNER.id);
  expect(count).toBe(1);
});

test("More ideas when the Mac is offline", async ({ page, signIn }) => {
  await seedOffice();
  await signIn();
  const ideas = page.getByRole("region", { name: /ideas/ });
  await ideas.getByRole("button", { name: "Get ideas" }).click();
  await expect(ideas.getByRole("status")).toHaveText(
    "Your Mac is offline, so new ideas will appear when it’s back. Your saved outfits still rotate.",
  );
});

test("weather line on Today, and Today still works when the forecast is unusable", async ({ page, signIn }) => {
  await admin
    .from("profiles")
    .update({ latitude: 42.36, longitude: -71.06, city_name: "Boston" })
    .eq("user_id", OWNER.id);
  await page.route("https://api.open-meteo.com/**", (r) =>
    r.fulfill({
      json: {
        daily: {
          temperature_2m_max: [47],
          temperature_2m_min: [38],
          precipitation_probability_max: [70],
          weather_code: [61],
        },
      },
    }),
  );
  await signIn();
  await expect(page.getByTestId("weather-line")).toHaveText("38° to 47°F, 70% chance of rain");

  await page.evaluate(() => localStorage.clear());
  await page.unroute("https://api.open-meteo.com/**");
  await page.route("https://api.open-meteo.com/**", (r) => r.fulfill({ json: { daily: {} } }));
  await page.reload();
  await expect(page.getByRole("radiogroup", { name: "Dressing for" })).toBeVisible();
  await expect(page.getByTestId("weather-line")).toHaveCount(0);
});

test("wishlist: add, overlap note, Do I need this?, I bought it moves it into the closet", async ({ page, signIn }) => {
  test.setTimeout(90_000);
  await seedItems([{ name: "White oxford shirt", category: "Tops", color_hex: "#f6f6f3" }]);
  worker = startFakeWorker();
  await waitForHeartbeat();
  await signIn("/shop?tab=wishlist");
  await page.getByRole("button", { name: "Add to wishlist" }).first().click();
  const sheet = page.getByRole("dialog", { name: "Add to wishlist" });
  await sheet.getByLabel("Name").fill("White oxford shirt, slim fit");
  await sheet.getByLabel("Category").selectOption("Tops");
  await sheet.getByLabel("Color").fill("White");
  await sheet.getByLabel("Price ($)").fill("39.90");
  await sheet.getByLabel("Link").fill("javascript:alert(1)");
  await sheet.getByRole("button", { name: "Add to wishlist" }).click();
  await expect(sheet.getByRole("alert")).toHaveText(/link doesn’t look right/);
  await sheet.getByLabel("Link").fill("uniqlo.com/us/en/p/E123");
  await sheet.getByRole("button", { name: "Add to wishlist" }).click();
  await expect(sheet).toBeHidden();

  const card = page.getByRole("listitem", { name: "White oxford shirt, slim fit" });
  await expect(card.getByRole("link", { name: "Open listing" })).toHaveAttribute(
    "href",
    "https://uniqlo.com/us/en/p/E123",
  );
  await expect(card.getByRole("link", { name: "Open listing" })).toHaveAttribute("rel", "noopener noreferrer");
  await expect(card).toContainText("$39.90 · uniqlo.com");
  await expect(card.locator(".overlap")).toHaveText("You own 1 similar: White oxford shirt.");

  await card.getByRole("button", { name: "Do I need this?" }).click();
  await expect(card.locator(".verdict .v-word")).toHaveText("Wait on it", { timeout: 25_000 });

  await card.getByRole("button", { name: "I bought it" }).click();
  const add = page.getByRole("dialog", { name: "Add clothes" });
  await expect(add.getByLabel("Name")).toHaveValue("White oxford shirt, slim fit");
  await expect(add.getByLabel("Price paid ($)")).toHaveValue("39.9");
  await add.getByRole("button", { name: "Add to closet" }).click();
  await expect(add).toBeHidden();
  await expect(card).toBeHidden();
  const { data: wish } = await admin.from("wishlist_items").select("status").eq("user_id", OWNER.id).single();
  expect(wish?.status).toBe("bought");
  const { data: items } = await admin.from("items").select("name,price_cents").eq("user_id", OWNER.id).order("name");
  expect(items).toContainEqual({ name: "White oxford shirt, slim fit", price_cents: 3990 });
});

test("wishlist Remove has Undo", async ({ page, signIn }) => {
  await admin.from("wishlist_items").insert({ user_id: OWNER.id, name: "Suede loafers", category: "Shoes" });
  await signIn("/shop?tab=wishlist");
  const card = page.getByRole("listitem", { name: "Suede loafers" });
  await card.getByRole("button", { name: "Remove" }).click();
  await expect(card).toBeHidden();
  await page.locator(".toast").getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("listitem", { name: "Suede loafers" })).toBeVisible();
});

test("What’s missing: ideas with price ranges, add one to the wishlist", async ({ page, signIn }) => {
  test.setTimeout(90_000);
  await seedOffice();
  worker = startFakeWorker();
  await waitForHeartbeat();
  await signIn("/shop?tab=missing");
  await page.getByRole("group", { name: "Occasion" }).getByRole("button", { name: "Office" }).click();
  await page.getByRole("button", { name: "Find what’s missing" }).click();
  const ideas = page.getByRole("list", { name: "Ideas" }).getByRole("listitem");
  await expect(ideas.first()).toBeVisible({ timeout: 30_000 });
  expect(await ideas.count()).toBeGreaterThanOrEqual(3);
  await expect(ideas.first().locator(".price")).toHaveText(/^\$\d+ to \$\d+$/);
  await expect(ideas.first()).toContainText(/Adds \d+ new office outfit/);
  await ideas.first().getByRole("button", { name: "Add to wishlist" }).click();
  await expect(ideas.first().getByRole("button", { name: "On your wishlist" })).toBeDisabled();
  const { count } = await admin
    .from("wishlist_items")
    .select("*", { count: "exact", head: true })
    .eq("user_id", OWNER.id);
  expect(count).toBe(1);
});

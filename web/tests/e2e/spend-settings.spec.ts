import { admin } from "./admin";
import { daysAgo, resetOwnerData, seedItems, seedWear, today } from "./data";
import { OWNER } from "./env";
import { expect, test } from "./fixtures";

test.beforeEach(resetOwnerData);

test("spend: month total, budget, 12 months, cost per wear", async ({ page, signIn }) => {
  const t = today();
  const firstOfMonth = `${t.slice(0, 7)}-01`;
  const ids = await seedItems([
    { name: "Boots", category: "Shoes", price_cents: 12000, bought_on: firstOfMonth },
    { name: "Shirt", category: "Tops", price_cents: 3950, bought_on: firstOfMonth },
    { name: "Old jeans", category: "Bottoms", price_cents: 6000, bought_on: "2020-01-15" }, // outside 12 months
    { name: "Mystery jacket", category: "Layers", price_cents: 9000, bought_on: null },
    { name: "Gift scarf", category: "Accessories", price_cents: null },
  ]);
  for (const n of [1, 2, 3]) await seedWear(daysAgo(n), null, [ids["Shirt"]!]);

  await signIn("/spend");
  await expect(page.getByTestId("month-total")).toHaveText("$159.50");
  await expect(page.getByText("of your $150 budget")).toBeVisible();
  await expect(page.getByTestId("budget-line")).toHaveText("$9.50 over budget");
  await expect(page.getByRole("meter", { name: "Budget used" })).toHaveAttribute("aria-valuenow", "100");
  await expect(page.getByTestId("year-total")).toHaveText("$159.50 total");
  await expect(page.getByRole("region", { name: "Earning their keep" })).toContainText("Shirt");
  await expect(page.getByRole("region", { name: "Earning their keep" })).toContainText("$13.17 per wear");
  const waiting = page.getByRole("region", { name: "Waiting for a wear" });
  await expect(waiting.getByRole("listitem").first()).toContainText("Mystery jacket");
  await expect(waiting).toContainText("Old jeans");
  await expect(page.getByText(/2 pieces have no price or purchase date/)).toBeVisible();

  // Raising the budget flips the line.
  await admin.from("profiles").update({ monthly_budget_cents: 20000 }).eq("user_id", OWNER.id);
  await page.reload();
  await expect(page.getByTestId("budget-line")).toHaveText("$40.50 left this month");
});

test("settings: save sizes and budget, find a city, delete everything", async ({ page, signIn }) => {
  await page.route("https://geocoding-api.open-meteo.com/**", (route) =>
    route.fulfill({
      json: {
        results: [
          {
            name: "Boston",
            latitude: 42.3584,
            longitude: -71.0598,
            timezone: "America/New_York",
            admin1: "Massachusetts",
            country: "United States",
          },
          {
            name: "Boston",
            latitude: 52.9739,
            longitude: -0.0266,
            timezone: "Europe/London",
            admin1: "England",
            country: "United Kingdom",
          },
        ],
      },
    }),
  );
  await seedItems([{ name: "Shirt", category: "Tops" }]);
  await signIn("/profile");
  const settings = page.getByRole("region", { name: "Settings" });
  await settings.getByLabel("Waist").fill("32");
  await settings.getByLabel("Fit preference").selectOption("slim");
  await settings.getByLabel("Height").fill(`5'9"`);
  await settings.getByLabel("Monthly clothing budget ($)").fill("200");
  await settings.getByLabel("Favorite stores").fill("Uniqlo, J.Crew, Uniqlo");
  await settings.getByRole("button", { name: "Save settings" }).click();
  await expect(page.locator(".toast")).toContainText("Settings saved");
  const { data: p } = await admin.from("profiles").select("*").eq("user_id", OWNER.id).single();
  expect(p).toMatchObject({
    fit_pref: "slim",
    height_cm: 175,
    monthly_budget_cents: 20000,
    favorite_stores: ["Uniqlo", "J.Crew"],
  });
  expect(p!.sizes).toMatchObject({ waist: "32" });

  await settings.getByLabel("Home city").fill("Boston");
  await settings.getByRole("button", { name: "Find" }).click();
  await settings.getByRole("button", { name: "Boston, England, United Kingdom" }).click();
  await expect(settings.getByText("Saved: Boston, England, United Kingdom")).toBeVisible();
  await expect(settings.getByLabel("Time zone")).toHaveValue("Europe/London");

  await page.reload();
  await expect(page.getByRole("region", { name: "Settings" }).getByLabel("Waist")).toHaveValue("32");

  const confirm = page.getByLabel("Type delete to confirm");
  const del = page.getByRole("button", { name: "Delete everything" });
  await expect(del).toBeDisabled();
  await confirm.fill("delete");
  await del.click();
  await expect(page).toHaveURL(/\/today$/);
  await expect(page.getByRole("heading", { name: "Your closet is empty" })).toBeVisible();
  const { count } = await admin.from("items").select("*", { count: "exact", head: true }).eq("user_id", OWNER.id);
  expect(count).toBe(0);
});

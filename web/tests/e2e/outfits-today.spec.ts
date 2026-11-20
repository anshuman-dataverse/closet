import { admin } from "./admin";
import { daysAgo, resetOwnerData, seedItems, seedOutfit, seedWear, today } from "./data";
import { OWNER } from "./env";
import { expect, test } from "./fixtures";

test.beforeEach(resetOwnerData);

test("build an outfit: needs 2 pieces and an occasion, names itself, orders pieces", async ({ page, signIn }) => {
  await seedItems([
    { name: "Grey chinos", category: "Bottoms", color_hex: "#8a8f98" },
    { name: "Navy oxford", category: "Tops", color_hex: "#1f2a48" },
  ]);
  await signIn("/outfits");
  await page.getByRole("button", { name: "Build an outfit" }).first().click();
  const sheet = page.getByRole("dialog", { name: "Build an outfit" });
  await sheet.getByRole("button", { name: "Grey chinos" }).click();
  await sheet.getByRole("button", { name: "Save outfit" }).click();
  await expect(sheet.getByRole("alert")).toHaveText(/at least two pieces/);
  await sheet.getByRole("button", { name: "Navy oxford" }).click();
  await expect(sheet.getByRole("button", { name: "Navy oxford" })).toHaveAttribute("aria-pressed", "true");
  await sheet.getByRole("group", { name: "Good for" }).getByRole("button", { name: "Office" }).click(); // turns off the default
  await sheet.getByRole("button", { name: "Save outfit" }).click();
  await expect(sheet.getByRole("alert")).toHaveText(/at least one occasion/);
  await sheet.getByRole("group", { name: "Good for" }).getByRole("button", { name: "College" }).click();
  await sheet.getByRole("button", { name: "Save outfit" }).click();
  // Tops come before Bottoms, so the default name starts with the shirt.
  await expect(page.getByRole("button", { name: "Navy oxford + Grey chinos", exact: true })).toBeVisible();
  await expect(page.locator(".ocard .pill")).toHaveText(["College"]);
});

test("Today: rotation, wear, undo, duplicate guard, you're wearing, recently worn", async ({ page, signIn }) => {
  const ids = await seedItems([
    { name: "Navy oxford", category: "Tops" },
    { name: "White oxford", category: "Tops" },
    { name: "Grey chinos", category: "Bottoms" },
    { name: "Sweater", category: "Layers", status: "laundry" },
  ]);
  const worn = await seedOutfit("Worn last week", [ids["Navy oxford"]!, ids["Grey chinos"]!], ["office"], 30_000);
  await seedOutfit("Never worn yet", [ids["White oxford"]!, ids["Grey chinos"]!], ["office"], 20_000);
  await seedOutfit("Has laundry", [ids["Navy oxford"]!, ids["Sweater"]!], ["office"], 10_000);
  await seedWear(daysAgo(5), worn, [ids["Navy oxford"]!, ids["Grey chinos"]!]);

  await signIn();
  await page.getByRole("radio", { name: "office" }).click();
  const pick = page.getByRole("region", { name: "Suggested outfit" });
  await expect(pick.getByRole("heading")).toHaveText("Never worn yet");
  await expect(pick.locator(".hangtag")).toHaveText("Never worn");
  await pick.getByRole("button", { name: "Next option" }).click();
  await expect(pick.getByRole("heading")).toHaveText("Worn last week");
  await expect(pick.locator(".hangtag")).toHaveText("Last worn 5 days ago");
  await pick.getByRole("button", { name: "Next option" }).click(); // laundry outfit is skipped → wraps
  await expect(pick.getByRole("heading")).toHaveText("Never worn yet");

  await pick.getByRole("button", { name: "Wear this" }).click();
  const toast = page.locator(".toast");
  await expect(toast).toContainText("Logged for today");
  await toast.getByRole("button", { name: "Undo" }).click();
  await expect(pick.getByRole("heading")).toHaveText("Never worn yet");

  await pick.getByRole("button", { name: "Wear this" }).click();
  const wearing = page.getByRole("region", { name: "Today’s outfit" });
  await expect(wearing.getByRole("heading")).toHaveText("Never worn yet");
  await expect(page.getByRole("region", { name: "Recently worn" }).getByRole("listitem").first()).toContainText(
    "Today",
  );

  // Same outfit again from Outfits → duplicate guard.
  await page.goto("/outfits");
  await page.getByRole("button", { name: "Wear Never worn yet today" }).click();
  await expect(page.locator(".toast")).toContainText("Already logged for today");
  const { count } = await admin.from("wear_logs").select("*", { count: "exact", head: true }).eq("user_id", OWNER.id);
  expect(count).toBe(2);

  await page.goto("/today");
  await wearing.getByRole("button", { name: "Pick something else" }).click();
  await expect(page.getByRole("region", { name: "Suggested outfit" })).toBeVisible();
  await page.reload();
  await page.getByRole("region", { name: "Today’s outfit" }).getByRole("button", { name: "Remove from log" }).click();
  // Removing today's wear puts it back to never worn, so it leads the rotation again.
  const again = page.getByRole("region", { name: "Suggested outfit" });
  await expect(again.getByRole("heading")).toHaveText("Never worn yet");
  await expect(again.locator(".hangtag")).toHaveText("Never worn");
});

test("outfit detail: log a past day, see it in history, remove it", async ({ page, signIn }) => {
  const ids = await seedItems([
    { name: "Navy oxford", category: "Tops" },
    { name: "Grey chinos", category: "Bottoms" },
  ]);
  const o = await seedOutfit("Office basic", [ids["Navy oxford"]!, ids["Grey chinos"]!]);
  await signIn(`/outfits?outfit=${o}`);
  const sheet = page.getByRole("dialog", { name: "Office basic" });
  await expect(sheet.getByText("Not worn yet.")).toBeVisible();
  await sheet.getByLabel("Another day").fill(daysAgo(2));
  await sheet.getByRole("button", { name: "Log this day" }).click();
  await expect(page.locator(".toast")).toContainText("Logged for that day");
  const history = sheet.getByRole("list", { name: "History" });
  await expect(history.getByRole("listitem")).toHaveCount(1);
  await history.getByRole("button", { name: "Remove" }).click();
  await expect(sheet.getByText("Not worn yet.")).toBeVisible();
  // Piece links open the item sheet in the closet.
  await sheet.getByRole("link", { name: "Navy oxford" }).click();
  await expect(page).toHaveURL(/\/closet\?item=/);
  await expect(page.getByRole("dialog", { name: "Navy oxford" })).toBeVisible();
  expect(today()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
});

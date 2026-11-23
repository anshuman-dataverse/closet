import type { ChildProcess } from "node:child_process";
import { admin } from "./admin";
import { resetOwnerData } from "./data";
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

test("a deal hunt runs on the Mac, shows picks, adds one to the wishlist, and deletes with Undo", async ({
  page,
  signIn,
}) => {
  test.setTimeout(90_000);
  worker = startFakeWorker();
  await waitForHeartbeat();
  await signIn("/shop?tab=hunts");
  await expect(page.getByText("Free search reads public product pages.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "New hunt" }).click();
  const sheet = page.getByRole("dialog", { name: "New hunt" });
  await sheet.getByRole("button", { name: "Start hunt" }).click();
  await expect(sheet.getByRole("alert")).toHaveText(/Say what you’re looking for/);
  await sheet.getByLabel("What").fill("white oxford shirt");
  await sheet.getByRole("group", { name: "Occasion" }).getByRole("button", { name: "Office" }).click();
  await sheet.getByLabel("Budget from ($)").fill("60"); // reversed on purpose: swapped
  await sheet.getByLabel("Budget to ($)").fill("25");
  await sheet.getByRole("button", { name: "Start hunt" }).click();
  await expect(sheet).toBeHidden();

  const card = page.getByRole("listitem", { name: "Hunt: white oxford shirt" });
  await expect(card.getByTestId("hunt-status")).toHaveText("2 picks", { timeout: 30_000 });
  await expect(card).toContainText("Office · $25 to $60");
  await expect(card).toContainText("H&M blocked automated reading.");
  const pick = card.getByRole("listitem", { name: "The Slim Oxford Shirt | White" });
  await expect(pick).toContainText("$39");
  await expect(pick).toContainText("29% off");
  await expect(pick.getByRole("link", { name: "The Slim Oxford Shirt | White" })).toHaveAttribute(
    "rel",
    "noopener noreferrer",
  );
  await expect(card.getByRole("listitem", { name: "Oxford Shirt", exact: true })).toContainText(
    "Your size is in stock",
  );
  const row = await admin.from("hunts").select("budget_min_cents, budget_max_cents").eq("user_id", OWNER.id).single();
  expect(row.data).toEqual({ budget_min_cents: 2500, budget_max_cents: 6000 });

  await pick.getByRole("button", { name: "Add to wishlist" }).click();
  await expect(pick.getByRole("button", { name: "On your wishlist" })).toBeDisabled();
  const wish = await admin.from("wishlist_items").select("name, price_cents, store").eq("user_id", OWNER.id).single();
  expect(wish.data).toEqual({ name: "The Slim Oxford Shirt | White", price_cents: 3900, store: "Everlane" });

  await card.getByRole("button", { name: "Delete" }).click();
  await expect(card).toBeHidden();
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("listitem", { name: "Hunt: white oxford shirt" }).getByTestId("hunt-status")).toHaveText(
    "2 picks",
  );
});

test("a watched wish that dropped in price shows a badge and the drop", async ({ page, signIn }) => {
  await admin.from("wishlist_items").insert({
    user_id: OWNER.id,
    name: "Navy chinos",
    price_cents: 6000,
    url: "https://www.gap.com/browse/product.do?pid=1",
    watch: true,
    target_price_cents: null,
    last_seen_price_cents: 4900,
    last_price_check_at: new Date().toISOString(),
    status: "wanted",
  });
  await signIn("/shop");
  await expect(page.getByLabel("1 price drop").filter({ visible: true })).toHaveCount(1); // phone tab bar or desktop nav
  await expect(page.getByRole("listitem", { name: "Navy chinos" }).getByTestId("price-drop")).toContainText(
    "Price dropped to $49 from $60",
  );
});

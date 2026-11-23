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
  await expect(page.getByText("Some stores block reading, so results vary.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "New hunt" }).click();
  const sheet = page.getByRole("dialog", { name: "New hunt" });
  await sheet.getByRole("button", { name: "Start hunt" }).click();
  await expect(sheet.getByRole("alert")).toHaveText(/Say what you’re looking for/);
  await sheet.getByLabel("What").fill("white oxford shirt");
  await sheet.getByRole("group", { name: "Occasion" }).getByRole("button", { name: "Office" }).click();
  await sheet.getByLabel("Budget from ($)").fill("60"); // reversed on purpose: swapped
  await sheet.getByLabel("Budget to ($)").fill("25");
  await sheet.getByRole("button", { name: "Start hunt" }).click();
  await expect(sheet.getByRole("alert")).toHaveText("Choose Menswear, Womenswear or Both."); // asked once
  await sheet
    .getByRole("group", { name: "Clothes I mostly wear" })
    .getByRole("button", { name: "Menswear", exact: true })
    .click();
  await sheet.getByRole("button", { name: "Start hunt" }).click();
  await expect(sheet).toBeHidden();
  const prof = await admin.from("profiles").select("wears").eq("user_id", OWNER.id).single();
  expect(prof.data?.wears).toBe("menswear");

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

test("shop a look: a complete set with its total, added to the wishlist in one tap", async ({ page, signIn }) => {
  test.setTimeout(90_000);
  worker = startFakeWorker();
  await waitForHeartbeat();
  await signIn("/shop?tab=hunts");
  await page.getByRole("button", { name: "Shop a look" }).click();
  const sheet = page.getByRole("dialog", { name: "Shop a look" });
  await sheet.getByRole("group", { name: "Occasion" }).getByRole("button", { name: "College" }).click();
  // Each piece's type can be picked; untouched slots stay on "Best for my closet".
  const top = sheet.getByRole("group", { name: "Top", exact: true });
  await expect(top.getByRole("button", { name: "Best for my closet" })).toHaveAttribute("aria-pressed", "true");
  await top.getByRole("button", { name: "Henley" }).click();
  await sheet.getByLabel("Total budget ($)").fill("260");
  await sheet
    .getByRole("group", { name: "Clothes I mostly wear" })
    .getByRole("button", { name: "Menswear", exact: true })
    .click();
  await sheet.getByRole("button", { name: "Shop the look" }).click();
  await expect(sheet).toBeHidden();

  const card = page.getByRole("listitem", { name: "Hunt: College look" });
  await expect(card).toContainText("1 complete look within $260.", { timeout: 30_000 });
  await expect(card.getByTestId("hunt-status")).toHaveText("1 look");
  const look = card.getByRole("region", { name: "Look 1" });
  await expect(look.getByRole("heading")).toHaveText("Look 1 · $255.80");
  for (const slot of ["Top", "Layer", "Bottoms", "Shoes"]) await expect(look).toContainText(slot);
  const row = await admin
    .from("hunts")
    .select("kind, look_mode, budget_max_cents, look_types")
    .eq("user_id", OWNER.id)
    .single();
  expect(row.data).toEqual({ kind: "look", look_mode: "new", budget_max_cents: 26000, look_types: { Tops: "henley" } });
  await expect(card).toContainText("Henley");

  // Change pieces reopens the sheet with this look's choices.
  await card.getByRole("button", { name: "Change pieces" }).click();
  await expect(top.getByRole("button", { name: "Henley" })).toHaveAttribute("aria-pressed", "true");
  await expect(sheet.getByLabel("Total budget ($)")).toHaveValue("260");
  await sheet.getByRole("button", { name: "Close", exact: true }).click();
  await expect(sheet).toBeHidden();

  await look.getByRole("button", { name: "Add all to wishlist" }).click();
  await expect(look.getByRole("button", { name: "Look is on your wishlist" })).toBeDisabled();
  const wishes = await admin.from("wishlist_items").select("name").eq("user_id", OWNER.id);
  expect(wishes.data?.map((w) => w.name).sort()).toEqual([
    "Italian Leather Sneaker",
    "Italian Merino Wool-Blend Crew-Neck Sweater",
    "Oxford Button-Down Shirt",
    "Straight Italian-Stretch Chino",
  ]);
});

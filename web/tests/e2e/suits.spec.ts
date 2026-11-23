import type { ChildProcess } from "node:child_process";
import path from "node:path";
import { admin } from "./admin";
import { resetOwnerData, seedItems } from "./data";
import { OWNER } from "./env";
import { expect, test } from "./fixtures";
import { waitForHeartbeat } from "./helpers-worker";
import { startFakeWorker, stopWorker } from "./worker-process";

const SHOT = path.join(__dirname, "fixtures", "shirt.jpg");
let worker: ChildProcess | undefined;
test.beforeEach(resetOwnerData);
test.afterEach(async () => {
  await stopWorker(worker);
  worker = undefined;
});

test("would it suit me: a screenshot is checked, explained, and added to the wishlist", async ({ page, signIn }) => {
  test.setTimeout(90_000);
  await seedItems([
    {
      name: "Grey chinos",
      category: "Bottoms",
      type: "chinos",
      color_name: "grey",
      formality: 3,
      occasions: ["office"],
    },
    {
      name: "Brown loafers",
      category: "Shoes",
      type: "loafers",
      color_name: "brown",
      formality: 4,
      occasions: ["office"],
    },
  ]);
  worker = startFakeWorker();
  await waitForHeartbeat();
  await signIn("/shop");
  await page.getByRole("button", { name: "Would it suit me?" }).click();
  const sheet = page.getByRole("dialog", { name: "Would it suit me?" });

  await sheet.getByRole("button", { name: "Check it" }).click();
  await expect(sheet.getByRole("alert")).toHaveText("Paste a product link or add a screenshot of the piece.");

  await sheet.getByTestId("suits-photo-input").setInputFiles(SHOT);
  await sheet.getByRole("group", { name: "Occasion" }).getByRole("button", { name: "Office" }).click();
  await sheet.getByRole("button", { name: "Check it" }).click();

  const box = sheet.getByRole("region", { name: "Would it suit me" });
  await expect(box).toBeVisible({ timeout: 30_000 });
  await expect(box).toContainText("Formality: The right formality for the office.");
  await expect(box).toContainText("Near your face: Analyze your style photos");
  await expect(sheet).toContainText("Read from your screenshot: knit polo in navy (read from the picture).");

  await sheet.getByRole("button", { name: "Add to wishlist" }).click();
  await expect(sheet).toBeHidden();
  await expect(page.getByRole("list", { name: "Your wishlist" })).toContainText("Navy knit polo");
  const row = await admin.from("wishlist_items").select("status, category, occasion").eq("user_id", OWNER.id).single();
  expect(row.data).toEqual({ status: "wanted", category: "Tops", occasion: "office" });
});

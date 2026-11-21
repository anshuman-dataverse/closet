import path from "node:path";
import { admin } from "./admin";
import { ownerFiles, resetOwnerData } from "./data";
import { OWNER } from "./env";
import { expect, test } from "./fixtures";

test.beforeEach(resetOwnerData);

const FIXTURE = path.join(__dirname, "fixtures", "shirt.jpg");

test("add a piece with a photo, then laundry, retire and delete it", async ({ page, signIn }) => {
  await signIn("/closet");
  await page.getByRole("button", { name: "Add your first piece" }).click();
  const sheet = page.getByRole("dialog", { name: "Add clothes" });
  await sheet.getByTestId("photo-input").setInputFiles(FIXTURE);
  // No worker in this test: the Mac is offline, so the piece is saved now and tagged later.
  await expect(sheet.getByTestId("photo-hint")).toHaveText(
    "Save it now, and the details will be suggested when your Mac is back.",
  );

  // Name is required.
  await sheet.getByRole("button", { name: "Add to closet" }).click();
  await expect(sheet.getByRole("alert").first()).toHaveText(/Give it a name/);

  await sheet.getByLabel("Name").fill("Navy tee");
  await sheet.getByLabel("Category").selectOption("Tops");
  await sheet.getByRole("group", { name: "Good for" }).getByRole("button", { name: "Office" }).click();
  await sheet.getByLabel("Price paid ($)").fill("39.50");
  await sheet.getByRole("button", { name: "Add to closet" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Added to your closet" })).toBeVisible();
  await expect(sheet).toBeHidden();

  const tile = page.getByRole("button", { name: /Navy tee/ });
  await expect(tile).toContainText("Not worn yet");
  await expect(tile.locator("img")).toHaveAttribute("src", /token=/); // signed URL to the private bucket
  const files = await ownerFiles();
  expect(files.filter((f) => f.endsWith("_thumb.jpg"))).toHaveLength(1);
  expect(files).toHaveLength(2);

  // In laundry → filter → Laundry done
  await tile.click();
  await page.getByRole("dialog", { name: "Navy tee" }).getByRole("button", { name: "In laundry" }).click();
  await expect(page.getByRole("button", { name: /Navy tee/ })).toBeHidden();
  await page.getByRole("group", { name: "Status" }).getByRole("button", { name: "In laundry (1)" }).click();
  await expect(page.getByRole("button", { name: /Navy tee/ })).toBeVisible();
  await page.getByRole("button", { name: "Laundry done" }).click();
  await expect(page.getByRole("button", { name: /Navy tee/ })).toBeHidden();
  await page.getByRole("group", { name: "Status" }).getByRole("button", { name: "Active" }).click();

  // Retire → Bring back
  await page.getByRole("button", { name: /Navy tee/ }).click();
  await page.getByRole("dialog", { name: "Navy tee" }).getByRole("button", { name: "Retire" }).click();
  await page.getByRole("group", { name: "Status" }).getByRole("button", { name: "Retired (1)" }).click();
  await page.getByRole("button", { name: /Navy tee/ }).click();
  await page.getByRole("dialog", { name: "Navy tee" }).getByRole("button", { name: "Bring back" }).click();
  await page.getByRole("group", { name: "Status" }).getByRole("button", { name: "Active" }).click();

  // Delete takes two taps and removes the files.
  await page.getByRole("button", { name: /Navy tee/ }).click();
  const edit = page.getByRole("dialog", { name: "Navy tee" });
  await edit.getByRole("button", { name: "Delete" }).click();
  await edit.getByRole("button", { name: "Tap again to delete" }).click();
  await expect(page.getByRole("heading", { name: "Nothing here yet" })).toBeVisible();
  await expect.poll(ownerFiles).toEqual([]);
});

test("starters and Save and add another make adding fast", async ({ page, signIn }) => {
  await signIn("/closet?add=1");
  const sheet = page.getByRole("dialog", { name: "Add clothes" });
  const starters = sheet.getByRole("group", { name: "Starters from your photos" });
  await starters.getByRole("button", { name: "Khaki chinos" }).click();
  await expect(sheet.getByLabel("Name")).toHaveValue("Khaki chinos");
  await expect(sheet.getByLabel("Category")).toHaveValue("Bottoms");
  await sheet.getByRole("button", { name: "Save and add another" }).click();
  await expect(sheet.getByLabel("Name")).toHaveValue("");
  await expect(starters.getByRole("button", { name: "Khaki chinos" })).toBeHidden(); // used starters drop off
  await starters.getByRole("button", { name: "Navy kurta" }).click();
  await sheet.getByRole("button", { name: "Add to closet" }).click();
  await expect(page.getByRole("button", { name: /Navy kurta/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Khaki chinos/ })).toBeVisible();
  const { count } = await admin.from("items").select("*", { count: "exact", head: true }).eq("user_id", OWNER.id);
  expect(count).toBe(2);
});

test("a photo that can't be decoded explains what to do", async ({ page, signIn }) => {
  await signIn("/closet?add=1");
  const sheet = page.getByRole("dialog", { name: "Add clothes" });
  await sheet
    .getByTestId("photo-input")
    .setInputFiles({ name: "x.jpg", mimeType: "image/jpeg", buffer: Buffer.from("nope") });
  await expect(sheet.getByRole("alert").first()).toHaveText("That photo couldn’t be opened. Try a JPEG or PNG.");
});

test("fit choices follow the category and what you wear", async ({ page, signIn }) => {
  await signIn("/closet");
  await page.getByRole("button", { name: "Add your first piece" }).click();
  const sheet = page.getByRole("dialog", { name: "Add clothes" });
  // Take photo opens the camera on a phone; Choose photo opens the library.
  await expect(sheet.getByTestId("camera-input")).toHaveAttribute("capture", "environment");
  await expect(sheet.getByRole("button", { name: "Take photo" })).toBeVisible();
  await expect(sheet.getByRole("button", { name: "Choose photo" })).toBeVisible();

  await sheet.getByLabel("Name").fill("Wide jeans");
  await sheet.getByLabel("Category").selectOption("Bottoms");
  const fit = sheet.getByRole("group", { name: "Fit" });
  await expect(fit.getByRole("button", { name: "Not sure" })).toHaveAttribute("aria-pressed", "true");
  await expect(fit.getByRole("button", { name: "Barrel" })).toBeVisible(); // no answer yet: every choice
  await fit.getByRole("button", { name: "Wide or baggy" }).click();
  await expect(fit.getByRole("button", { name: "Wide or baggy" })).toHaveAttribute("aria-pressed", "true");
  await sheet.getByRole("button", { name: "Add to closet" }).click();
  await expect(sheet).toBeHidden();
  const row = await admin.from("items").select("fit").eq("user_id", OWNER.id).single();
  expect(row.data?.fit).toBe("wide");

  // Shoes have no fit; switching away drops a fit that no longer applies.
  await page.getByRole("button", { name: /Wide jeans/ }).click();
  const edit = page.getByRole("dialog", { name: "Wide jeans" });
  await expect(edit.getByRole("group", { name: "Fit" }).getByRole("button", { name: "Wide or baggy" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await edit.getByLabel("Category").selectOption("Shoes");
  await expect(edit.getByRole("group", { name: "Fit" })).toBeHidden();
  await edit.getByLabel("Category").selectOption("Tops");
  await expect(edit.getByRole("group", { name: "Fit" }).getByRole("button", { name: "Not sure" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await edit.getByRole("button", { name: "Save changes" }).click();
  await expect(edit).toBeHidden();
  const after = await admin.from("items").select("fit, category").eq("user_id", OWNER.id).single();
  expect(after.data).toEqual({ fit: null, category: "Tops" });

  // "Clothes I mostly wear: Menswear" hides womenswear-only choices.
  await page.goto("/profile");
  const settings = page.getByRole("region", { name: "Settings" });
  await settings.getByLabel("Clothes I mostly wear").selectOption("menswear");
  await settings.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByRole("status").filter({ hasText: /saved/i })).toBeVisible();
  await page.goto("/closet?add=1");
  const add = page.getByRole("dialog", { name: "Add clothes" });
  await add.getByLabel("Category").selectOption("Bottoms");
  const menswear = add.getByRole("group", { name: "Fit" });
  await expect(menswear.getByRole("button", { name: "Flared" })).toBeVisible();
  await expect(menswear.getByRole("button", { name: "Barrel" })).toBeHidden();
});

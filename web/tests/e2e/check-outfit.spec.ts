import type { ChildProcess } from "node:child_process";
import { resetOwnerData, seedItems } from "./data";
import { expect, test } from "./fixtures";
import { waitForHeartbeat } from "./helpers-worker";
import { startFakeWorker, stopWorker } from "./worker-process";

let worker: ChildProcess | undefined;
test.beforeEach(resetOwnerData);
test.afterEach(async () => {
  await stopWorker(worker);
  worker = undefined;
});

test("check an outfit: a verdict in words with every check explained", async ({ page, signIn }) => {
  test.setTimeout(90_000);
  await seedItems([
    {
      name: "Light blue oxford shirt",
      category: "Tops",
      type: "oxford shirt",
      color_name: "light blue",
      formality: 3,
      fit: "regular",
      occasions: ["office"],
    },
    {
      name: "Navy chinos",
      category: "Bottoms",
      type: "chinos",
      color_name: "navy",
      formality: 3,
      fit: "slim",
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
    {
      name: "Grey hoodie",
      category: "Layers",
      type: "hoodie",
      color_name: "grey",
      formality: 1,
      fit: "oversized",
      occasions: ["home"],
    },
    {
      name: "Grey joggers",
      category: "Bottoms",
      type: "joggers",
      color_name: "grey",
      formality: 1,
      fit: "relaxed",
      occasions: ["home"],
    },
  ]);
  worker = startFakeWorker();
  await waitForHeartbeat();
  await signIn("/outfits");
  await page.getByRole("button", { name: "Check an outfit" }).click();
  const sheet = page.getByRole("dialog", { name: "Build an outfit" });
  await sheet.getByRole("group", { name: "Good for" }).getByRole("button", { name: "Office" }).click();
  for (const n of ["Light blue oxford shirt", "Navy chinos", "Brown loafers"])
    await sheet.getByRole("button", { name: n }).click();
  await sheet.getByRole("button", { name: "Check it" }).click();
  const box = sheet.getByTestId("outfit-check");
  await expect(box).toContainText("Strong", { timeout: 20_000 });
  await expect(box).toContainText("Complete outfit: Top, bottom and shoes are all there.");
  await expect(box).toContainText("Fit balance:");
  await expect(box).toContainText("Weather: No forecast for the day");

  // Swap in the hoodie and joggers: loose over loose, too casual for the office.
  for (const n of ["Light blue oxford shirt", "Navy chinos", "Grey hoodie", "Grey joggers"])
    await sheet.getByRole("button", { name: n }).click();
  await sheet.getByRole("button", { name: "Check it" }).click();
  await expect(box).toContainText("Rethink it", { timeout: 20_000 });
  await expect(box).toContainText("loose over loose");
});

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

test("sample pieces: add, see them badged and used for ideas, never as spend, remove in one tap", async ({
  page,
  signIn,
}) => {
  test.setTimeout(90_000);
  worker = startFakeWorker();
  await waitForHeartbeat();
  await signIn("/profile");
  const settings = page.getByRole("region", { name: "Shopping and money" });
  await settings.getByRole("button", { name: "Add sample pieces" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Added 21 sample pieces" })).toBeVisible();
  const { count } = await admin
    .from("items")
    .select("*", { count: "exact", head: true })
    .eq("user_id", OWNER.id)
    .eq("is_sample", true);
  expect(count).toBe(21);

  await page.goto("/closet");
  await expect(page.getByRole("button", { name: /Navy blazer/ })).toContainText("Sample");

  await page.goto("/today");
  const ideas = page.getByRole("region", { name: /ideas/ });
  await expect(ideas.locator("article.combo").first()).toBeVisible({ timeout: 30_000 }); // samples pass the bar

  await page.goto("/spend");
  await expect(page.getByText("Navy blazer")).toHaveCount(0); // never counted as spend

  await page.goto("/profile");
  await settings.getByRole("button", { name: "Remove sample pieces (21)" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Removed 21 sample pieces" })).toBeVisible();
  const after = await admin.from("items").select("*", { count: "exact", head: true }).eq("user_id", OWNER.id);
  expect(after.count).toBe(0);
});

import path from "node:path";
import type { ChildProcess } from "node:child_process";
import { admin } from "./admin";
import { ownerFiles, resetOwnerData } from "./data";
import { OWNER } from "./env";
import { expect, type Page, test } from "./fixtures";
import { startFakeWorker, stopWorker } from "./worker-process";

const FIXTURE = path.join(__dirname, "fixtures", "shirt.jpg");
let worker: ChildProcess | undefined;

test.beforeEach(resetOwnerData);
test.afterEach(async () => stopWorker(worker));

/** Waits for the fake worker's first heartbeat (the pill is also hidden while status loads, so check the DB). */
async function waitForHeartbeat() {
  await expect
    .poll(async () => (await admin.from("workers").select("id").eq("user_id", OWNER.id)).data?.length ?? 0, {
      timeout: 30_000,
    })
    .toBeGreaterThan(0);
}

async function macOnline(page: Page) {
  await expect(page.getByRole("button", { name: "Mac offline" })).toBeHidden();
}

test("photo suggestions fill only the fields you haven't touched", async ({ page, signIn }) => {
  test.setTimeout(90_000);
  worker = startFakeWorker();
  await waitForHeartbeat();
  await signIn("/closet?add=1");
  await macOnline(page);
  const sheet = page.getByRole("dialog", { name: "Add clothes" });
  await sheet.getByLabel("Name").fill("My work shirt");
  await sheet.getByTestId("photo-input").setInputFiles(FIXTURE);
  await expect(sheet.getByTestId("photo-hint")).toHaveText("Filled in from your photo. Check the details.", {
    timeout: 25_000,
  });
  await expect(sheet.getByLabel("Name")).toHaveValue("My work shirt"); // typed first, so kept
  await expect(sheet.getByLabel("Type")).toHaveValue("Oxford shirt");
  await expect(sheet.getByLabel("Color")).toHaveValue("Navy");
  await expect(sheet.getByLabel("Pattern")).toHaveValue("solid");
  await expect(sheet.getByLabel("Formality")).toHaveValue("3");
  await expect(sheet.getByRole("group", { name: "Good for" }).getByRole("button", { name: "Office" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await sheet.getByRole("button", { name: "Add to closet" }).click();
  await expect(sheet).toBeHidden();

  const { data } = await admin.from("items").select("*").eq("user_id", OWNER.id);
  expect(data).toHaveLength(1);
  expect(data![0]).toMatchObject({
    name: "My work shirt",
    type: "Oxford shirt",
    color_hex: "#1f2a48",
    suggestions: null,
  });

  // Reviewed in the form, so the item sheet has nothing pending.
  await page.getByRole("button", { name: /My work shirt/ }).click();
  await expect(page.getByRole("region", { name: "Suggestions from your Mac" })).toBeHidden();
});

test("offline: save now, the Mac suggests later, Apply fills it in", async ({ page, signIn }) => {
  test.setTimeout(90_000);
  await signIn("/closet?add=1");
  const sheet = page.getByRole("dialog", { name: "Add clothes" });
  await sheet.getByTestId("photo-input").setInputFiles(FIXTURE);
  await expect(sheet.getByTestId("photo-hint")).toHaveText(
    "Save it now, and the details will be suggested when your Mac is back.",
  );
  await sheet.getByLabel("Name").fill("Later shirt");
  await sheet.getByRole("button", { name: "Add to closet" }).click();
  await expect(sheet).toBeHidden();
  const { data: queued } = await admin.from("jobs").select("status").eq("user_id", OWNER.id).eq("kind", "tag_item");
  expect(queued).toEqual([{ status: "queued" }]);

  worker = startFakeWorker();
  await expect
    .poll(
      async () => (await admin.from("items").select("tags_status").eq("user_id", OWNER.id).single()).data?.tags_status,
      {
        timeout: 30_000,
      },
    )
    .toBe("ready");
  await page.reload();
  await page.getByRole("button", { name: /Later shirt/ }).click();
  const box = page.getByRole("region", { name: "Suggestions from your Mac" });
  await expect(box).toContainText("Type: Oxford shirt");
  await expect(box.getByRole("checkbox", { name: /Type/ })).toBeChecked(); // empty fields are picked
  await box.getByRole("button", { name: "Apply" }).click();
  await expect(box).toBeHidden();
  const { data } = await admin
    .from("items")
    .select("type,color_name,suggestions,name")
    .eq("user_id", OWNER.id)
    .single();
  expect(data).toMatchObject({ type: "Oxford shirt", color_name: "Navy", suggestions: null, name: "Later shirt" });
});

test("closing Add clothes after picking a photo removes the draft and its files", async ({ page, signIn }) => {
  await signIn("/closet?add=1");
  const sheet = page.getByRole("dialog", { name: "Add clothes" });
  await sheet.getByTestId("photo-input").setInputFiles(FIXTURE);
  await expect(sheet.getByTestId("photo-hint")).not.toHaveText(/Preparing|Uploading/);
  await expect.poll(async () => (await ownerFiles()).length).toBe(2);
  await sheet.getByRole("button", { name: "Close", exact: true }).click();
  await expect.poll(ownerFiles).toEqual([]);
  const { count } = await admin.from("items").select("*", { count: "exact", head: true }).eq("user_id", OWNER.id);
  expect(count).toBe(0);
});

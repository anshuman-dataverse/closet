import path from "node:path";
import type { ChildProcess } from "node:child_process";
import { admin } from "./admin";
import { ownerFiles, resetOwnerData } from "./data";
import { OWNER } from "./env";
import { expect, test } from "./fixtures";
import { waitForHeartbeat } from "./helpers-worker";
import { startFakeWorker, stopWorker } from "./worker-process";

const FIXTURE = path.join(__dirname, "fixtures", "shirt.jpg");
let worker: ChildProcess | undefined;

test.beforeEach(async () => {
  await resetOwnerData();
  await admin
    .from("profiles")
    .update({ analysis: null, undertone_override: null, contrast_override: null })
    .eq("user_id", OWNER.id);
});
test.afterEach(async () => {
  await stopWorker(worker);
  worker = undefined;
});

test("style photos → analyze → what suits you → change undertone → remove a photo", async ({ page, signIn }) => {
  test.setTimeout(120_000);
  worker = startFakeWorker();
  await waitForHeartbeat();
  await signIn("/profile");
  const photos = page.getByRole("region", { name: "Style photos" });
  await expect(photos.getByText("Your photos are analyzed on your Mac and never sent to an AI service.")).toBeVisible();
  const analyze = photos.getByRole("button", { name: "Analyze my photos" });
  await expect(analyze).toBeDisabled();

  await photos.getByTestId("style-photo-input").setInputFiles(FIXTURE); // first suggested kind: face close-up
  await expect(photos.getByRole("list", { name: "Your style photos" }).getByRole("listitem")).toHaveCount(1);
  await expect(photos.getByRole("button", { name: "Add a front photo" })).toBeVisible();
  await photos.getByTestId("style-photo-input").setInputFiles(FIXTURE);
  await expect(photos.getByRole("list", { name: "Your style photos" }).getByRole("listitem")).toHaveCount(2);
  await expect(photos.getByText("2 of 6")).toBeVisible();

  await analyze.click();
  const suits = page.getByRole("region", { name: "What suits you" });
  await expect(suits).toBeVisible({ timeout: 60_000 });
  const best = suits.getByRole("list", { name: "Your best colors" }).getByRole("listitem");
  expect(await best.count()).toBeGreaterThanOrEqual(6);
  await expect(suits.getByRole("list", { name: "Use carefully" }).locator(".sw-why").first()).toHaveText(/\.$/);
  await expect(suits.getByLabel("Face shape tips")).toContainText("Oval");
  await expect(suits.getByLabel("Face shape tips")).toContainText("Frames");
  await expect(suits.getByText("An estimate from your photos. You can change it.")).toBeVisible();

  const before = await best.allInnerTexts();
  const { data: prof } = await admin.from("profiles").select("analysis").eq("user_id", OWNER.id).single();
  const computed = (prof!.analysis as { computed: { undertone: string } }).computed.undertone;
  const other = computed === "cool" ? "warm" : "cool";
  await suits.getByLabel("Undertone").selectOption(other);
  await expect(suits.locator(".pills")).toContainText(`${other[0]!.toUpperCase()}${other.slice(1)} undertone`, {
    timeout: 30_000,
  });
  expect(await best.allInnerTexts()).not.toEqual(before);
  const { data: after } = await admin.from("profiles").select("undertone_override").eq("user_id", OWNER.id).single();
  expect(after!.undertone_override).toBe(other);

  const first = photos.getByRole("list", { name: "Your style photos" }).getByRole("listitem").first();
  await first.getByRole("button", { name: /^Remove the/ }).click();
  await first.getByRole("button", { name: /^Tap again to remove/ }).click();
  await expect(photos.getByRole("list", { name: "Your style photos" }).getByRole("listitem")).toHaveCount(1);
  await expect.poll(async () => (await ownerFiles()).filter((f) => f.includes("/style/")).length).toBe(2);
});

test("analyze needs a face close-up and a front photo, and says so", async ({ page, signIn }) => {
  await signIn("/profile");
  const photos = page.getByRole("region", { name: "Style photos" });
  await expect(photos.getByText("Add a face close-up and a front photo first.")).toBeVisible();
  await expect(page.getByRole("region", { name: "What suits you" })).toHaveCount(0);
});

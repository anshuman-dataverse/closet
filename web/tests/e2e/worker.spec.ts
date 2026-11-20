import type { ChildProcess } from "node:child_process";
import { admin, backdateWorker, resetWorkerState } from "./admin";
import { OWNER } from "./env";
import { expect, test } from "./fixtures";
import { startFakeWorker, stopWorker } from "./worker-process";

let worker: ChildProcess | undefined;

test.beforeEach(resetWorkerState);
test.afterEach(async () => stopWorker(worker));

test("Mac offline → queued work waits → Mac back → ping round trip → Mac offline again", async ({ page, signIn }) => {
  test.setTimeout(90_000);
  await signIn("/profile");
  const pill = page.getByRole("button", { name: "Mac offline" });

  // No heartbeat yet: the pill shows, and queued work is listed.
  await expect(pill).toBeVisible();
  await admin.from("jobs").insert({ kind: "ping", user_id: OWNER.id, payload: { nonce: "waiting" } });
  await pill.click();
  const sheet = page.getByRole("dialog", { name: "Your Mac is offline" });
  await expect(sheet.getByText("Connection test")).toBeVisible();
  await expect(sheet.getByText(/work without your Mac/)).toBeVisible();
  await sheet.getByRole("button", { name: "Close" }).click();

  // Worker starts: heartbeat clears the pill and the waiting job runs.
  worker = startFakeWorker();
  await expect(pill).toBeHidden({ timeout: 30_000 });
  await expect(page.getByTestId("worker-state")).toHaveText("Online");
  await expect
    .poll(async () => (await admin.from("jobs").select("status").eq("user_id", OWNER.id)).data?.[0]?.status, {
      timeout: 20_000,
    })
    .toBe("done");

  // "Test your Mac" makes a full round trip through the queue.
  await page.getByRole("button", { name: "Test your Mac" }).click();
  await expect(page.getByTestId("ping-result")).toHaveText(/Your Mac answered in/, { timeout: 20_000 });

  // Worker stops and its heartbeat goes stale (>2 min): the pill comes back.
  await stopWorker(worker);
  await backdateWorker(3 * 60_000);
  await expect(pill).toBeVisible({ timeout: 35_000 });
  await expect(page.getByTestId("worker-state")).toHaveText("Offline");
});

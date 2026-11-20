import { expect } from "@playwright/test";
import { admin } from "./admin";
import { OWNER } from "./env";

/** Waits for the fake worker's first heartbeat (the pill is also hidden while status loads). */
export async function waitForHeartbeat() {
  await expect
    .poll(async () => (await admin.from("workers").select("id").eq("user_id", OWNER.id)).data?.length ?? 0, {
      timeout: 30_000,
    })
    .toBeGreaterThan(0);
}

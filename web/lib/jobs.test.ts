import { describe, expect, it } from "vitest";
import { isFinished, jobPhase, PHASE_LABEL, waitForJob } from "./jobs";
import type { Db } from "./supabase/types";

describe("job status flow", () => {
  it("queued shows 'Waiting for your Mac' only while the Mac is offline", () => {
    expect(PHASE_LABEL[jobPhase("queued", false)]).toBe("Queued");
    expect(PHASE_LABEL[jobPhase("queued", true)]).toBe("Waiting for your Mac");
  });
  it("running, done and failed pass through", () => {
    expect(jobPhase("running", true)).toBe("running");
    expect(jobPhase("done", true)).toBe("done");
    expect(jobPhase("failed", false)).toBe("failed");
  });
  it("finished means done or failed", () => {
    expect(["queued", "running", "done", "failed"].filter((s) => isFinished(s as never))).toEqual(["done", "failed"]);
  });
});

function fakeDb(statuses: string[]): Db {
  let i = 0;
  const single = async () => ({ data: { id: "j", status: statuses[Math.min(i++, statuses.length - 1)] }, error: null });
  return { from: () => ({ select: () => ({ eq: () => ({ single }) }) }) } as unknown as Db;
}

describe("waitForJob", () => {
  it("returns once the job is done", async () => {
    const row = await waitForJob(fakeDb(["queued", "running", "done"]), "j", { intervalMs: 1, timeoutMs: 1000 });
    expect(row?.status).toBe("done");
  });
  it("returns the last row on timeout", async () => {
    const row = await waitForJob(fakeDb(["queued"]), "j", { intervalMs: 5, timeoutMs: 30 });
    expect(row?.status).toBe("queued");
  });
});

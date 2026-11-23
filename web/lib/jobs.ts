// Job queue helpers shared by every screen that asks the Mac for work.
import type { Database, Json } from "@/lib/database.types";
import type { Db } from "@/lib/supabase/types";

export type JobRow = Database["public"]["Tables"]["jobs"]["Row"];
export type JobStatus = Database["public"]["Enums"]["job_status"];
export type JobKind =
  | "ping"
  | "tag_item"
  | "read_label"
  | "embed_wish"
  | "analyze_profile"
  | "suggest_outfits"
  | "rate_outfit"
  | "check_wish"
  | "suits_me"
  | "find_gaps"
  | "run_hunt"
  | "price_check"
  | "train_ranker"
  | "backup";

/** What the UI shows for a job, given the worker's state. */
export type JobPhase = "queued" | "waiting" | "running" | "done" | "failed";

export function jobPhase(status: JobStatus, workerOffline: boolean): JobPhase {
  if (status === "queued") return workerOffline ? "waiting" : "queued";
  return status;
}

export const PHASE_LABEL: Record<JobPhase, string> = {
  queued: "Queued",
  waiting: "Waiting for your Mac",
  running: "Working…",
  done: "Done",
  failed: "Failed",
};

export const isFinished = (s: JobStatus): boolean => s === "done" || s === "failed";

export async function enqueueJob(
  db: Db,
  kind: JobKind,
  payload: { [key: string]: Json | undefined } = {},
  priority = 0,
): Promise<JobRow> {
  const { data, error } = await db.from("jobs").insert({ kind, payload, priority }).select("*").single();
  if (error || !data) throw new Error(error?.message ?? "Couldn’t queue the job.");
  return data;
}

/** Polls until the job finishes or the timeout passes. Returns the latest row either way. */
export async function waitForJob(
  db: Db,
  id: string,
  {
    timeoutMs = 20_000,
    intervalMs = 700,
    signal,
  }: { timeoutMs?: number; intervalMs?: number; signal?: AbortSignal } = {},
): Promise<JobRow | null> {
  const end = Date.now() + timeoutMs;
  let last: JobRow | null = null;
  while (Date.now() < end && !signal?.aborted) {
    const { data } = await db.from("jobs").select("*").eq("id", id).single();
    if (data) {
      last = data;
      if (isFinished(data.status)) return data;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return last;
}

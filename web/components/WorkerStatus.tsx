"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { JobKind } from "@/lib/jobs";
import { supabase } from "@/lib/supabase/client";
import { type Capabilities, isOffline, readCapabilities } from "@/lib/worker-status";

export const KIND_LABEL: Record<JobKind, string> = {
  ping: "Connection test",
  tag_item: "Reading a clothing photo",
  read_label: "Reading a clothing label",
  embed_wish: "Reading a wishlist photo",
  analyze_profile: "Analyzing your style photos",
  suggest_outfits: "Outfit ideas",
  rate_outfit: "Checking an outfit",
  check_wish: "“Do I need this?” check",
  suits_me: "“Would it suit me?” check",
  find_gaps: "What’s missing",
  run_hunt: "Deal hunt",
  price_check: "Price check",
  train_ranker: "Training your picks model",
  backup: "Backup",
};

type State = {
  loaded: boolean;
  offline: boolean;
  lastSeenAt: string | null;
  version: string | null;
  capabilities: Capabilities;
  queued: { kind: string; count: number }[];
  lastBackupAt: string | null;
  lastBackup: unknown;
  refresh: () => void;
};

const Ctx = createContext<State | null>(null);

type WorkerRow = { last_seen_at: string; version: string | null; capabilities: unknown };
type Snapshot = {
  worker: WorkerRow | null;
  queued: { kind: string }[];
  lastBackupAt: string | null;
  lastBackup: unknown;
};

async function fetchSnapshot(): Promise<Snapshot> {
  const db = supabase();
  const [w, q, b] = await Promise.all([
    db.from("workers").select("last_seen_at,version,capabilities").order("last_seen_at", { ascending: false }).limit(1),
    db.from("jobs").select("kind").eq("status", "queued").limit(200),
    db
      .from("jobs")
      .select("finished_at,result")
      .eq("kind", "backup")
      .eq("status", "done")
      .order("finished_at", { ascending: false })
      .limit(1),
  ]);
  return {
    worker: w.data?.[0] ?? null,
    queued: q.data ?? [],
    lastBackupAt: b.data?.[0]?.finished_at ?? null,
    lastBackup: b.data?.[0]?.result ?? null,
  };
}

export function useWorkerStatus(): State {
  const s = useContext(Ctx);
  if (!s) throw new Error("useWorkerStatus must be used inside WorkerStatusProvider");
  return s;
}

export function WorkerStatusProvider({ children }: { children: React.ReactNode }) {
  const [loaded, setLoaded] = useState(false);
  const [worker, setWorker] = useState<WorkerRow | null>(null);
  const [queuedRows, setQueuedRows] = useState<{ kind: string }[]>([]);
  const [lastBackupAt, setLastBackupAt] = useState<string | null>(null);
  const [lastBackup, setLastBackup] = useState<unknown>(null);
  const [now, setNow] = useState(0); // set on first load; nothing reads it before then

  const apply = useCallback((s: Snapshot) => {
    setWorker(s.worker);
    setQueuedRows(s.queued);
    setLastBackupAt(s.lastBackupAt);
    setLastBackup(s.lastBackup);
    setNow(Date.now());
    setLoaded(true);
  }, []);
  const refresh = useCallback(() => {
    fetchSnapshot().then(apply, () => {}); // offline browser: keep the last known state
  }, [apply]);

  useEffect(() => {
    refresh();
    const db = supabase();
    const channel = db
      .channel("worker-status")
      .on("postgres_changes", { event: "*", schema: "public", table: "workers" }, refresh)
      .on("postgres_changes", { event: "*", schema: "public", table: "jobs" }, refresh)
      .subscribe();
    // Re-check age even when nothing changes, and poll in case Realtime drops.
    const tick = setInterval(() => setNow(Date.now()), 15_000);
    const poll = setInterval(refresh, 30_000);
    const onVisible = () => {
      if (document.visibilityState === "visible") refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(tick);
      clearInterval(poll);
      document.removeEventListener("visibilitychange", onVisible);
      void db.removeChannel(channel);
    };
  }, [refresh]);

  const value = useMemo<State>(() => {
    const counts = new Map<string, number>();
    for (const r of queuedRows) counts.set(r.kind, (counts.get(r.kind) ?? 0) + 1);
    return {
      loaded,
      offline: isOffline(worker?.last_seen_at, now),
      lastSeenAt: worker?.last_seen_at ?? null,
      version: worker?.version ?? null,
      capabilities: readCapabilities(worker?.capabilities),
      queued: [...counts].map(([kind, count]) => ({ kind, count })),
      lastBackupAt,
      lastBackup,
      refresh,
    };
  }, [loaded, worker, queuedRows, lastBackupAt, lastBackup, now, refresh]);

  return <Ctx value={value}>{children}</Ctx>;
}

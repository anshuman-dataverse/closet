"use client";

import { useState } from "react";
import { useToast } from "@/components/Toast";
import { useWorkerStatus } from "@/components/WorkerStatus";
import { enqueueJob, waitForJob } from "@/lib/jobs";
import { supabase } from "@/lib/supabase/client";
import { backupSummary, compatText, seenAgo } from "@/lib/worker-status";

export function WorkerPanel() {
  const s = useWorkerStatus();
  const toast = useToast();
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState("");
  const [backingUp, setBackingUp] = useState(false);

  const backupNow = async () => {
    setBackingUp(true);
    try {
      const db = supabase();
      const job = await enqueueJob(db, "backup", {}, 1);
      toast("Backup started on your Mac.");
      const done = await waitForJob(db, job.id, { timeoutMs: 180_000 });
      if (done?.status === "done") toast("Backup done.");
      else if (done?.status === "failed") toast(`Backup failed: ${done.error ?? "unknown error"}`);
      s.refresh();
    } catch {
      toast("Couldn’t start the backup. Check your connection and try again.");
    } finally {
      setBackingUp(false);
    }
  };

  const test = async () => {
    setTesting(true);
    setResult("");
    const started = performance.now();
    try {
      const db = supabase();
      const nonce = Math.random().toString(36).slice(2, 10);
      const job = await enqueueJob(db, "ping", { nonce });
      const done = await waitForJob(db, job.id, { timeoutMs: 20_000 });
      if (done?.status === "done") {
        setResult(`Your Mac answered in ${((performance.now() - started) / 1000).toFixed(1)} s.`);
      } else if (done?.status === "failed") {
        setResult(`Your Mac couldn’t run the test: ${done.error ?? "unknown error"}.`);
      } else {
        setResult("No answer yet. The test stays queued and runs when your Mac is back.");
      }
    } catch {
      toast("Couldn’t queue the test. Check your connection and try again.");
    } finally {
      setTesting(false);
    }
  };

  const caps = s.capabilities;
  return (
    <section className="block" aria-labelledby="worker-h">
      <div className="block-head">
        <h2 id="worker-h">Your Mac</h2>
      </div>
      {!s.loaded ? (
        <p className="muted">Checking…</p>
      ) : (
        <dl className="kv">
          <dt>Status</dt>
          <dd data-testid="worker-state">{s.offline ? "Offline" : "Online"}</dd>
          <dt>Last seen</dt>
          <dd>{seenAgo(s.lastSeenAt)}</dd>
          <dt>Deal search</dt>
          <dd>{caps.searxng ? "Ready" : "Not running"}</dd>
          <dt>Local phrasing</dt>
          <dd>{caps.ollama ? "Ready" : "Off"}</dd>
          <dt>Outfit model</dt>
          <dd data-testid="compat-state">{compatText(caps.compat)}</dd>
          <dt>Last backup</dt>
          <dd data-testid="last-backup">
            {s.lastBackupAt
              ? [seenAgo(s.lastBackupAt), backupSummary(s.lastBackup)].filter(Boolean).join(" · ")
              : "None yet"}
          </dd>
        </dl>
      )}
      <div className="row">
        <button type="button" className="btn" onClick={test} disabled={testing}>
          {testing ? "Testing…" : "Test your Mac"}
        </button>
        <button type="button" className="btn" onClick={backupNow} disabled={backingUp || s.offline}>
          {backingUp ? "Backing up…" : "Back up now"}
        </button>
      </div>
      <p className="hint" role="status" data-testid="ping-result">
        {result}
      </p>
    </section>
  );
}

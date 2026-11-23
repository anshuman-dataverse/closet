"use client";
/* eslint-disable @next/next/no-img-element -- store product images */

import { useState } from "react";
import { Chips } from "@/components/Chips";
import { EmptyState } from "@/components/EmptyState";
import { LoadGate } from "@/components/Loading";
import { Sheet } from "@/components/Sheet";
import { useToast } from "@/components/Toast";
import { useWorkerStatus } from "@/components/WorkerStatus";
import { deleteHunt, rerunHunt, saveWish, startHunt, useCloset } from "@/lib/closet/store";
import { type Hunt, type HuntResult, huntStatus, normalizeBudget, percentOff, sizeNote } from "@/lib/domain/hunts";
import { budgetRange, centsToInput, formatCents, parseDollars } from "@/lib/domain/money";
import { type Occasion, OCCASIONS } from "@/lib/occasions";
import { useSheetParam } from "@/lib/use-sheet-param";
import { seenAgo } from "@/lib/worker-status";

export const PRICES_CHANGE = "Prices change. Check the store page before buying.";
export const FREE_NOTE = "Free search reads public product pages. Some stores block it, so results vary.";

type Draft = { what: string; occasion: Occasion | ""; min: string; max: string; notes: string };

function Pick({ r, hunt }: { r: HuntResult; hunt: Hunt }) {
  const s = useCloset();
  const toast = useToast();
  const onList = s.wishes.some((w) => w.url === r.url);
  const off = percentOff(r.price_cents, r.was_price_cents);
  const add = async () => {
    try {
      await saveWish({
        id: crypto.randomUUID(),
        name: r.title.slice(0, 120),
        url: r.url,
        store: r.store,
        image_url: r.image_url,
        price_cents: r.price_cents,
        occasion: hunt.occasion,
        status: "wanted",
      });
      toast("Added to your wishlist");
    } catch (e) {
      toast((e as Error).message);
    }
  };
  return (
    <li className="hunt-pick" aria-label={r.title}>
      {r.image_url && <img className="wish-img" src={r.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" />}
      <div className="hunt-pick-body">
        <a className="link hunt-pick-title" href={r.url} target="_blank" rel="noopener noreferrer">
          {r.title}
        </a>
        <p className="price">
          {r.price_cents != null ? formatCents(r.price_cents) : "No price"}
          {r.was_price_cents != null && off != null && (
            <>
              {" "}
              <s className="muted">{formatCents(r.was_price_cents)}</s> <span className="off">{off}% off</span>
            </>
          )}
          {r.store && <span className="muted"> · {r.store}</span>}
        </p>
        {r.why && <p className="small">{r.why}</p>}
        <p className="muted small">
          {[r.quality, sizeNote(r.size_available), `Checked ${seenAgo(r.checked_at)}`].filter(Boolean).join(" · ")}
        </p>
        <button type="button" className="btn sm" onClick={add} disabled={onList}>
          {onList ? "On your wishlist" : "Add to wishlist"}
        </button>
      </div>
    </li>
  );
}

function HuntCard({ h }: { h: Hunt }) {
  const worker = useWorkerStatus();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const status = huntStatus(h, worker.offline);
  const remove = async () => {
    try {
      const undo = await deleteHunt(h.id);
      toast("Hunt deleted", { action: "Undo", onAction: () => void undo().catch((e: Error) => toast(e.message)) });
    } catch (e) {
      toast((e as Error).message);
    }
  };
  const again = async () => {
    setBusy(true);
    try {
      await rerunHunt(h.id);
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const meta = [
    h.occasion && OCCASIONS.find((o) => o.id === h.occasion)?.label,
    (h.budget_min_cents != null || h.budget_max_cents != null) && budgetRange(h.budget_min_cents, h.budget_max_cents),
  ].filter(Boolean);
  return (
    <li className="card" aria-label={`Hunt: ${h.query}`}>
      <h3>{h.query}</h3>
      {meta.length > 0 && <p className="muted small">{meta.join(" · ")}</p>}
      <p className={`small${h.status === "running" ? " thinking" : ""}`} role="status" data-testid="hunt-status">
        {status}
      </p>
      {h.summary && <p className="overlap">{h.summary}</p>}
      {h.results.length > 0 && (
        <ul className="hunt-picks" aria-label="Picks">
          {h.results.map((r) => (
            <Pick key={r.id} r={r} hunt={h} />
          ))}
        </ul>
      )}
      <div className="row">
        <button type="button" className="btn sm" onClick={again} disabled={busy || h.status === "running"}>
          {h.status === "failed" ? "Retry" : "Run again"}
        </button>
        <button type="button" className="btn sm" onClick={remove}>
          Delete
        </button>
      </div>
    </li>
  );
}

function HuntSheet({ open, onClose, initial }: { open: boolean; onClose: () => void; initial: Draft }) {
  const toast = useToast();
  const [f, setF] = useState<Draft>(initial);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [openedFor, setOpenedFor] = useState(false);
  if (open !== openedFor) {
    setOpenedFor(open);
    if (open) {
      setF(initial);
      setErr("");
      setBusy(false);
    }
  }
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setF((x) => ({ ...x, [k]: v }));
  const go = async () => {
    const what = f.what.trim();
    if (!what) return setErr("Say what you’re looking for, like “white oxford shirt”.");
    const lo = f.min.trim() ? parseDollars(f.min) : null;
    const hi = f.max.trim() ? parseDollars(f.max) : null;
    if ((f.min.trim() && lo === null) || (f.max.trim() && hi === null))
      return setErr("Enter budgets as numbers, like 25.");
    const b = normalizeBudget(lo, hi);
    setBusy(true);
    try {
      await startHunt({
        query: what.slice(0, 200),
        occasion: f.occasion || null,
        budget_min_cents: b.min,
        budget_max_cents: b.max,
        notes: f.notes.trim() || null,
      });
      toast("Hunt started on your Mac");
      onClose();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="New hunt"
      actions={
        <button type="button" className="btn primary" onClick={go} disabled={busy}>
          {busy ? "Starting…" : "Start hunt"}
        </button>
      }
    >
      <label className="field">
        <span>What</span>
        <input
          type="text"
          value={f.what}
          onChange={(e) => set("what", e.target.value)}
          placeholder="White oxford shirt"
          maxLength={200}
          autoComplete="off"
        />
      </label>
      <fieldset className="field">
        <legend>Occasion</legend>
        <Chips
          label="Occasion"
          wrap
          options={OCCASIONS}
          value={f.occasion}
          onChange={(o) => set("occasion", f.occasion === o ? "" : o)}
        />
      </fieldset>
      <div className="field-row">
        <label className="field">
          <span>Budget from ($)</span>
          <input
            type="text"
            inputMode="decimal"
            value={f.min}
            onChange={(e) => set("min", e.target.value)}
            placeholder="25"
          />
        </label>
        <label className="field">
          <span>Budget to ($)</span>
          <input
            type="text"
            inputMode="decimal"
            value={f.max}
            onChange={(e) => set("max", e.target.value)}
            placeholder="60"
          />
        </label>
      </div>
      <label className="field">
        <span>Notes</span>
        <input type="text" value={f.notes} onChange={(e) => set("notes", e.target.value)} maxLength={200} />
      </label>
      <p className="hint">Your sizes, colors, favorite stores and what you mostly wear are added for you.</p>
      {err && (
        <p className="err" role="alert">
          {err}
        </p>
      )}
    </Sheet>
  );
}

export function HuntsPanel() {
  const s = useCloset();
  const { params, open, close } = useSheetParam();
  const sheetOpen = params.get("new") === "hunt";
  const initial: Draft = {
    what: params.get("what") ?? "",
    occasion: (OCCASIONS.find((o) => o.id === params.get("occ"))?.id ?? "") as Occasion | "",
    min: centsToInput(Number(params.get("min")) || null),
    max: centsToInput(Number(params.get("max")) || null),
    notes: "",
  };
  if (s.status !== "ready") return <LoadGate s={s} />;
  return (
    <>
      <div className="row">
        <button type="button" className="btn primary" onClick={() => open("new", "hunt")}>
          New hunt
        </button>
      </div>
      <p className="muted small">
        {PRICES_CHANGE} {FREE_NOTE}
      </p>
      {s.hunts.length === 0 ? (
        <EmptyState title="No hunts yet">
          Try something like “white oxford shirt for the office, $25 to $60”.
        </EmptyState>
      ) : (
        <ul className="cards" aria-label="Hunts">
          {s.hunts.map((h) => (
            <HuntCard key={h.id} h={h} />
          ))}
        </ul>
      )}
      <HuntSheet open={sheetOpen} onClose={close} initial={initial} />
    </>
  );
}

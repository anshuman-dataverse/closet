"use client";
/* eslint-disable @next/next/no-img-element -- store product images */

import { useState } from "react";
import { Chips } from "@/components/Chips";
import { EmptyState } from "@/components/EmptyState";
import { LoadGate } from "@/components/Loading";
import { Sheet } from "@/components/Sheet";
import { useToast } from "@/components/Toast";
import { useWorkerStatus } from "@/components/WorkerStatus";
import { deleteHunt, rerunHunt, saveProfile, saveWish, startHunt, useCloset } from "@/lib/closet/store";
import { isWears, type Wears, WEARS } from "@/lib/domain/fit";
import { cleanPicks, lookSlots, lookTypesText } from "@/lib/domain/looks";
import {
  foundBySlot,
  type Hunt,
  type HuntResult,
  huntStatus,
  lookSets,
  normalizeBudget,
  percentOff,
  sizeNote,
} from "@/lib/domain/hunts";
import { budgetRange, centsToInput, formatCents, parseDollars } from "@/lib/domain/money";
import { type Occasion, OCCASIONS } from "@/lib/occasions";
import { useSheetParam } from "@/lib/use-sheet-param";
import { seenAgo } from "@/lib/worker-status";

export const PRICES_CHANGE = "Prices change. Check the store page before buying.";
export const FREE_NOTE = "Some stores block reading, so results vary.";

/** Hunts need to know whose clothes to search for. Asked once, saved to Settings. */
function WearsAsk({ value, onChange }: { value: Wears | ""; onChange: (w: Wears) => void }) {
  const s = useCloset();
  if (isWears(s.profile?.wears)) return null;
  return (
    <fieldset className="field">
      <legend>Clothes I mostly wear</legend>
      <Chips
        label="Clothes I mostly wear"
        wrap
        options={WEARS}
        value={value || ([] as readonly Wears[])}
        onChange={onChange}
      />
      <span className="hint">So hunts skip the other section’s products. Saved to Settings.</span>
    </fieldset>
  );
}

/** Saves the answer if it was just given; returns an error message when it's still missing. */
async function ensureWears(current: string | null | undefined, picked: Wears | ""): Promise<string> {
  if (isWears(current)) return "";
  if (!picked) return "Choose Menswear, Womenswear or Both.";
  await saveProfile({ wears: picked });
  return "";
}

type Draft = { what: string; occasion: Occasion | ""; min: string; max: string; notes: string };

function Pick({ r, hunt, slot }: { r: HuntResult; hunt: Hunt; slot?: string | null }) {
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
        {slot && <p className="muted small">{slot}</p>}
        <a className="link hunt-pick-title" href={r.url ?? undefined} target="_blank" rel="noopener noreferrer">
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
        {r.url && (
          <button type="button" className="btn sm" onClick={add} disabled={onList}>
            {onList ? "On your wishlist" : "Add to wishlist"}
          </button>
        )}
      </div>
    </li>
  );
}

function LookResults({ h }: { h: Hunt }) {
  const s = useCloset();
  const toast = useToast();
  const sets = lookSets(h.results);
  const found = sets.length ? [] : foundBySlot(h.results);
  const addAll = async (pieces: HuntResult[]) => {
    try {
      for (const r of pieces) {
        if (s.wishes.some((w) => w.url === r.url)) continue;
        await saveWish({
          id: crypto.randomUUID(),
          name: r.title.slice(0, 120),
          url: r.url,
          store: r.store,
          image_url: r.image_url,
          price_cents: r.price_cents,
          occasion: h.occasion,
          status: "wanted",
        });
      }
      toast("Look added to your wishlist");
    } catch (e) {
      toast((e as Error).message);
    }
  };
  return (
    <>
      {sets.map((set) => (
        <section key={set.no} className="look" aria-label={`Look ${set.no}`}>
          <h4>
            Look {set.no} · {formatCents(set.total)}
            {set.toBuy.length < set.pieces.length ? " to buy" : ""}
          </h4>
          <ul className="hunt-picks">
            {set.pieces.map((r) =>
              r.owned_item_id ? (
                <li key={r.id} className="hunt-pick" aria-label={r.title}>
                  <div className="hunt-pick-body">
                    <p className="muted small">{r.slot}</p>
                    <p className="hunt-pick-title">{r.title}</p>
                    <p className="muted small">From your closet</p>
                  </div>
                </li>
              ) : (
                <Pick key={r.id} r={r} hunt={h} slot={r.slot} />
              ),
            )}
          </ul>
          {set.toBuy.length > 0 && (
            <button
              type="button"
              className="btn sm primary"
              onClick={() => void addAll(set.toBuy)}
              disabled={set.toBuy.every((r) => s.wishes.some((w) => w.url === r.url))}
            >
              {set.toBuy.every((r) => s.wishes.some((w) => w.url === r.url))
                ? "Look is on your wishlist"
                : "Add all to wishlist"}
            </button>
          )}
        </section>
      ))}
      {found.map(([slot, rs]) => (
        <section key={slot} className="look" aria-label={`Found: ${slot}`}>
          <h4>{slot}: found</h4>
          <ul className="hunt-picks">
            {rs.map((r) => (
              <Pick key={r.id} r={r} hunt={h} />
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}

function HuntCard({ h, onChange }: { h: Hunt; onChange: (h: Hunt) => void }) {
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
    h.kind === "look" && lookTypesText(h.look_types),
  ].filter(Boolean);
  return (
    <li className="card" aria-label={`Hunt: ${h.query}`}>
      <h3>{h.query}</h3>
      {meta.length > 0 && <p className="muted small">{meta.join(" · ")}</p>}
      <p className={`small${h.status === "running" ? " thinking" : ""}`} role="status" data-testid="hunt-status">
        {status}
      </p>
      {h.summary && <p className="overlap">{h.summary}</p>}
      {h.kind === "look" ? <LookResults h={h} /> : null}
      {h.kind !== "look" && h.results.length > 0 && (
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
        {h.kind === "look" && (
          <button type="button" className="btn sm" onClick={() => onChange(h)} disabled={h.status === "running"}>
            Change pieces
          </button>
        )}
        <button type="button" className="btn sm" onClick={remove}>
          Delete
        </button>
      </div>
    </li>
  );
}

function HuntSheet({ open, onClose, initial }: { open: boolean; onClose: () => void; initial: Draft }) {
  const toast = useToast();
  const cl = useCloset();
  const [wears, setWears] = useState<Wears | "">("");
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
      const w = await ensureWears(cl.profile?.wears, wears);
      if (w) {
        setBusy(false);
        return setErr(w);
      }
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
      <WearsAsk value={wears} onChange={setWears} />
      <label className="field">
        <span>Notes</span>
        <input type="text" value={f.notes} onChange={(e) => set("notes", e.target.value)} maxLength={200} />
      </label>
      <p className="hint">Your sizes, colors and stores are used for you.</p>
      {err && (
        <p className="err" role="alert">
          {err}
        </p>
      )}
    </Sheet>
  );
}

type LookDraft = { occasion: Occasion; max: string; mode: "new" | "own"; picks: Record<string, string> };
const BLANK_LOOK: LookDraft = { occasion: "office", max: "", mode: "new", picks: {} };

function draftFrom(h: Hunt | null): LookDraft {
  if (!h) return BLANK_LOOK;
  const occasion = (OCCASIONS.find((o) => o.id === h.occasion)?.id ?? "office") as Occasion;
  const t = h.look_types;
  const picks =
    t && typeof t === "object" && !Array.isArray(t)
      ? Object.fromEntries(Object.entries(t).filter((e): e is [string, string] => typeof e[1] === "string"))
      : {};
  return {
    occasion,
    max: centsToInput(h.budget_max_cents),
    mode: h.look_mode === "own" ? "own" : "new",
    picks: cleanPicks(occasion, picks) ?? {},
  };
}

function LookSheet({ open, onClose, from }: { open: boolean; onClose: () => void; from: Hunt | null }) {
  const toast = useToast();
  const cl = useCloset();
  const [wears, setWears] = useState<Wears | "">("");
  const [f, setF] = useState<LookDraft>(BLANK_LOOK);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [openedFor, setOpenedFor] = useState(false);
  if (open !== openedFor) {
    setOpenedFor(open);
    if (open) {
      setErr("");
      setBusy(false);
      setF(draftFrom(from));
    }
  }
  const go = async () => {
    const max = f.max.trim() ? parseDollars(f.max) : null;
    if (f.max.trim() && max === null) return setErr("Enter the total budget as a number, like 250.");
    setBusy(true);
    try {
      const w = await ensureWears(cl.profile?.wears, wears);
      if (w) {
        setBusy(false);
        return setErr(w);
      }
      const occ = OCCASIONS.find((o) => o.id === f.occasion)?.label ?? f.occasion;
      await startHunt({
        query: `${occ} look`,
        occasion: f.occasion,
        budget_min_cents: null,
        budget_max_cents: max,
        notes: null,
        kind: "look",
        look_mode: f.mode,
        look_types: cleanPicks(f.occasion, f.picks),
      });
      toast("Shopping the look on your Mac");
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
      title="Shop a look"
      actions={
        <button type="button" className="btn primary" onClick={go} disabled={busy}>
          {busy ? "Starting…" : "Shop the look"}
        </button>
      }
    >
      <fieldset className="field">
        <legend>Occasion</legend>
        <Chips
          label="Occasion"
          wrap
          options={OCCASIONS}
          value={f.occasion}
          onChange={(o) => setF((x) => ({ ...x, occasion: o, picks: {} }))}
        />
      </fieldset>
      {lookSlots(f.occasion).map((sl) => (
        <fieldset key={sl.category} className="field">
          <legend>{sl.label}</legend>
          <Chips
            label={sl.label}
            wrap
            options={[{ id: "", label: "Best for my closet" }, ...sl.options]}
            value={f.picks[sl.category] ?? ""}
            onChange={(t) =>
              setF((x) => {
                const picks = { ...x.picks };
                if (t) picks[sl.category] = t;
                else delete picks[sl.category];
                return { ...x, picks };
              })
            }
          />
        </fieldset>
      ))}
      <label className="field">
        <span>Total budget ($)</span>
        <input
          type="text"
          inputMode="decimal"
          value={f.max}
          onChange={(e) => setF((x) => ({ ...x, max: e.target.value }))}
          placeholder="250"
        />
      </label>
      <WearsAsk value={wears} onChange={setWears} />
      <fieldset className="field">
        <legend>Pieces</legend>
        <Chips
          label="Pieces"
          wrap
          options={[
            { id: "new" as const, label: "All new" },
            { id: "own" as const, label: "Use what I own" },
          ]}
          value={f.mode}
          onChange={(m) => setF((x) => ({ ...x, mode: m }))}
        />
      </fieldset>
      <p className="hint">
        Your Mac plans every piece in colors that go together and suit you, then shops each one. “Best for my closet”
        picks the type you own the fewest of, so a look doesn’t buy what you already have. A look is shown only when
        every piece is found within your total.
      </p>
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
  const [lookFrom, setLookFrom] = useState<Hunt | null>(null);
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
        <button
          type="button"
          className="btn"
          onClick={() => {
            setLookFrom(null);
            open("new", "look");
          }}
        >
          Shop a look
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
            <HuntCard
              key={h.id}
              h={h}
              onChange={(x) => {
                setLookFrom(x);
                open("new", "look");
              }}
            />
          ))}
        </ul>
      )}
      <HuntSheet open={sheetOpen} onClose={close} initial={initial} />
      <LookSheet open={params.get("new") === "look"} onClose={close} from={lookFrom} />
    </>
  );
}

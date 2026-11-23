"use client";

import Link from "next/link";
import { useState } from "react";
import { Chips, toggle } from "@/components/Chips";
import { ConfirmButton } from "@/components/ConfirmButton";
import { Flatlay, PieceCell } from "@/components/Piece";
import { Sheet } from "@/components/Sheet";
import { useToast } from "@/components/Toast";
import { useWearActions } from "@/components/useWearActions";
import { useWorkerStatus } from "@/components/WorkerStatus";
import { deleteOutfit, saveOutfit, useCloset, useDerived } from "@/lib/closet/store";
import type { Item } from "@/lib/closet/types";
import { shortDate } from "@/lib/domain/dates";
import { CATEGORY_ORDER, orderPieces, outfitName, outfitPieces, validateOutfit } from "@/lib/domain/outfit";
import { sortLogsNewest } from "@/lib/domain/wear";
import { enqueueJob, waitForJob } from "@/lib/jobs";
import { type Occasion, OCCASIONS } from "@/lib/occasions";
import { supabase } from "@/lib/supabase/client";
import { useOccasion } from "@/lib/use-occasion";

const OCC_LABEL = Object.fromEntries(OCCASIONS.map((o) => [o.id, o.label])) as Record<Occasion, string>;

/** Build or edit an outfit (SPEC 4.3). */
export function OutfitBuilderSheet({
  open,
  outfitId,
  onClose,
  onSaved,
}: {
  open: boolean;
  outfitId: string | null;
  onClose: () => void;
  onSaved?: (id: string) => void;
}) {
  const s = useCloset();
  const d = useDerived(s);
  const toast = useToast();
  const [today] = useOccasion();
  const existing = outfitId ? s.outfits.find((o) => o.id === outfitId) : undefined;

  const [sel, setSel] = useState<string[]>([]);
  const [occs, setOccs] = useState<Occasion[]>([]);
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [rating, setRating] = useState<Rating | null>(null);
  const [checking, setChecking] = useState("");
  const worker = useWorkerStatus();
  const [openedFor, setOpenedFor] = useState<string | undefined>(undefined);
  const key = open ? (outfitId ?? "new") : undefined;
  if (key !== openedFor) {
    setOpenedFor(key);
    if (open) {
      setRating(null);
      setChecking("");
      setSel(existing ? [...existing.itemIds] : []);
      setOccs(existing ? [...existing.occasions] : [today]);
      setName(existing?.name ?? "");
      setErr("");
      setBusy(false);
    }
  }

  // Active pieces, plus any retired / in-laundry ones already in this outfit.
  const pool = s.items.filter((i) => i.status === "active" || sel.includes(i.id));
  const groups = CATEGORY_ORDER.map((c) => [c, pool.filter((i) => i.category === c)] as const).filter(
    ([, l]) => l.length,
  );
  const other = pool.filter((i) => !i.category);
  const chosen = orderPieces(sel.map((id) => d.byId.get(id)).filter((x): x is Item => !!x));

  const save = async () => {
    const v = validateOutfit(sel, occs);
    if (v) return setErr(v);
    setBusy(true);
    setErr("");
    try {
      const id = await saveOutfit({
        id: existing?.id ?? null,
        name,
        occasions: occs,
        itemIds: chosen.map((i) => i.id),
      });
      toast("Outfit saved");
      onClose();
      onSaved?.(id);
    } catch (e) {
      setErr((e as Error).message);
      setBusy(false);
    }
  };

  const check = async () => {
    if (sel.length < 2) return setErr("Pick at least two pieces to check.");
    if (worker.offline) return setErr("Your Mac is offline. Checking runs on your Mac, so try again when it’s back.");
    setErr("");
    setRating(null);
    setChecking("Your Mac is checking it…");
    try {
      const db = supabase();
      const job = await enqueueJob(
        db,
        "rate_outfit",
        { item_ids: chosen.map((i) => i.id), occasion: occs[0] ?? today, date: d.today },
        6,
      );
      const done = await waitForJob(db, job.id, { timeoutMs: 20_000 });
      if (done?.status === "done") {
        setRating(parseRating(done.result));
        setChecking("");
      } else
        setChecking(
          done?.status === "failed"
            ? (done.error ?? "Your Mac couldn’t check it.")
            : "Still checking. Try again in a moment.",
        );
    } catch {
      setChecking("Couldn’t ask your Mac. Check your connection and try again.");
    }
  };

  const tile = (i: Item) => (
    <button
      key={i.id}
      type="button"
      className="pick-tile"
      aria-pressed={sel.includes(i.id)}
      onClick={() => setSel((x) => toggle(x, i.id))}
    >
      <span className="tile-ph">
        <PieceCell item={i} bare />
      </span>
      <span>{i.name}</span>
    </button>
  );

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={existing ? "Edit outfit" : "Build an outfit"}
      actions={
        <>
          {existing && (
            <ConfirmButton
              onConfirm={async () => {
                try {
                  await deleteOutfit(existing.id);
                  toast("Outfit deleted");
                  onClose();
                } catch (e) {
                  setErr((e as Error).message);
                }
              }}
            >
              Delete
            </ConfirmButton>
          )}
          <span className="grow" />
          <span className="muted small" aria-live="polite">
            {sel.length} {sel.length === 1 ? "piece" : "pieces"}
          </span>
          <button type="button" className="btn" disabled={!!checking && !rating} onClick={() => void check()}>
            Check it
          </button>
          <button type="button" className="btn primary" disabled={busy} onClick={save}>
            {busy ? "Saving…" : existing ? "Save changes" : "Save outfit"}
          </button>
        </>
      }
    >
      <p className="muted" style={{ margin: 0 }}>
        {pool.length ? "Tap the pieces that go together." : "Add clothes to your closet first."}
      </p>
      <div className="picker">
        {groups.map(([c, l]) => (
          <section key={c} aria-label={c}>
            <h3>{c}</h3>
            <div className="pick-grid">{l.map(tile)}</div>
          </section>
        ))}
        {other.length > 0 && (
          <section aria-label="Other">
            <h3>Other</h3>
            <div className="pick-grid">{other.map(tile)}</div>
          </section>
        )}
      </div>
      <label className="field">
        <span>Name (optional)</span>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={
            outfitName({ name: null }, chosen) === "Untitled outfit"
              ? "Blue oxford and grey chinos"
              : outfitName({ name: null }, chosen)
          }
          autoComplete="off"
          maxLength={80}
        />
      </label>
      <fieldset className="field">
        <legend>Good for</legend>
        <Chips label="Good for" wrap options={OCCASIONS} value={occs} onChange={(o) => setOccs((x) => toggle(x, o))} />
      </fieldset>
      {checking && (
        <p className="muted thinking" role="status">
          {checking}
        </p>
      )}
      {rating && <RatingBox r={rating} />}
      <p className="err" role="alert">
        {err}
      </p>
    </Sheet>
  );
}

/** Outfit details: pieces, wear it (today or a past day), history (SPEC 4.3). */
export function OutfitDetailSheet({
  open,
  outfitId,
  onClose,
  onEdit,
}: {
  open: boolean;
  outfitId: string | null;
  onClose: () => void;
  onEdit: (id: string) => void;
}) {
  const s = useCloset();
  const d = useDerived(s);
  const [current] = useOccasion();
  const { wear, unwear } = useWearActions();
  const o = outfitId ? s.outfits.find((x) => x.id === outfitId) : undefined;
  const [wearOcc, setWearOcc] = useState<Occasion>(current);
  const [day, setDay] = useState("");
  const [openedFor, setOpenedFor] = useState<string | undefined>(undefined);
  const key = open ? (outfitId ?? "") : undefined;
  if (key !== openedFor) {
    setOpenedFor(key);
    if (open && o) {
      setWearOcc(o.occasions.includes(current) ? current : (o.occasions[0] ?? current));
      setDay(d.today);
    }
  }
  if (!o)
    return (
      <Sheet open={open} onClose={onClose} title="Outfit">
        <p className="muted">This outfit no longer exists.</p>
      </Sheet>
    );

  const pieces = outfitPieces(o, d.byId);
  const history = sortLogsNewest(s.logs.filter((l) => l.outfit_id === o.id)).slice(0, 12);

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={outfitName(o, pieces)}
      actions={
        <>
          <span className="grow" />
          <button type="button" className="btn" onClick={() => onEdit(o.id)}>
            Edit outfit
          </button>
        </>
      }
    >
      <div className="pills">
        {o.occasions.map((x) => (
          <span key={x} className="pill">
            {OCC_LABEL[x]}
          </span>
        ))}
      </div>
      <div style={{ margin: "12px 0" }}>
        <Flatlay pieces={pieces} />
      </div>
      <ul className="piece-list">
        {pieces.map((p) => (
          <li key={p.id}>
            <Link className="link" href={`/closet?item=${p.id}`}>
              {p.name}
            </Link>
            {p.status !== "active" && (
              <span className="muted small"> ({p.status === "laundry" ? "in laundry" : "retired"})</span>
            )}
          </li>
        ))}
      </ul>
      <h3>Wear it</h3>
      <Chips label="Occasion" wrap options={OCCASIONS} value={wearOcc} onChange={setWearOcc} />
      <div className="row">
        <button
          type="button"
          className="btn primary"
          onClick={async () => {
            onClose();
            await wear(o, wearOcc, d.today);
          }}
        >
          Wear today
        </button>
        <label className="inline-date">
          <span className="sr">Another day</span>
          <input type="date" value={day} max={d.today} onChange={(e) => setDay(e.target.value)} />
        </label>
        <button
          type="button"
          className="btn"
          disabled={!day || day > d.today}
          onClick={() => void wear(o, wearOcc, day, day === d.today)}
        >
          Log this day
        </button>
      </div>
      <h3>History</h3>
      {history.length ? (
        <ul className="log" aria-label="History">
          {history.map((l) => (
            <li key={l.id}>
              <span className="log-date">{l.worn_on === d.today ? "Today" : shortDate(l.worn_on, d.today)}</span>
              <span className="log-name">{OCC_LABEL[l.occasion]}</span>
              <span />
              <button type="button" className="link" onClick={() => void unwear(l.id)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Not worn yet.</p>
      )}
    </Sheet>
  );
}

type RatingCheck = { key: string; label: string; ok: boolean | null; detail: string };
type Rating = { verdict: "strong" | "works" | "rethink"; headline: string; checks: RatingCheck[] };

function parseRating(raw: unknown): Rating | null {
  const r = raw as Partial<Rating> | null;
  if (!r || !r.verdict || !Array.isArray(r.checks)) return null;
  return { verdict: r.verdict, headline: String(r.headline ?? ""), checks: r.checks };
}

const MARK = { true: "✓", false: "✕", null: "–" } as const;

/** The verdict in words and every check with its reason (no made-up percentages). */
function RatingBox({ r }: { r: Rating }) {
  const cls = r.verdict === "strong" ? "good" : r.verdict === "works" ? "wait" : "bad";
  return (
    <section className={`verdict ${cls}`} aria-label="Outfit check" data-testid="outfit-check">
      <p>
        <span className="v-word">
          {r.verdict === "strong" ? "Strong" : r.verdict === "works" ? "It works" : "Rethink it"}
        </span>
      </p>
      <p className="small">{r.headline}</p>
      <ul className="checks">
        {r.checks.map((c) => (
          <li key={c.key} className={c.ok === false ? "fail" : c.ok === null ? "skip" : "pass"}>
            <span aria-hidden="true">{MARK[String(c.ok) as "true" | "false" | "null"]}</span>{" "}
            <strong>{c.label}:</strong> {c.detail}
          </li>
        ))}
      </ul>
    </section>
  );
}

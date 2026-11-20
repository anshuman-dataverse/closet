"use client";

import Link from "next/link";
import { useState } from "react";
import { Chips } from "@/components/Chips";
import { EmptyState } from "@/components/EmptyState";
import { HangTag } from "@/components/HangTag";
import { LoadGate } from "@/components/Loading";
import { OutfitBuilderSheet, OutfitDetailSheet } from "@/components/OutfitSheets";
import { Flatlay } from "@/components/Piece";
import { useWearActions } from "@/components/useWearActions";
import { useCloset, useDerived } from "@/lib/closet/store";
import { lastWornText } from "@/lib/domain/dates";
import { outfitName, outfitPieces } from "@/lib/domain/outfit";
import { leastRecentlyWorn } from "@/lib/domain/rotation";
import { NO_WEAR } from "@/lib/domain/wear";
import { type Occasion, OCCASIONS } from "@/lib/occasions";
import { useOccasion } from "@/lib/use-occasion";
import { useSheetParam } from "@/lib/use-sheet-param";

const OCC_LABEL = Object.fromEntries(OCCASIONS.map((o) => [o.id, o.label])) as Record<Occasion, string>;

export function OutfitsView() {
  const s = useCloset();
  const d = useDerived(s);
  const [current] = useOccasion();
  const { wear } = useWearActions();
  const { params, open, close } = useSheetParam();
  const [occ, setOcc] = useState<Occasion | "any">("any");

  const all = s.outfits.filter((o) => o.itemIds.length > 0);
  const list = leastRecentlyWorn(occ === "any" ? all : all.filter((o) => o.occasions.includes(occ)), d.stats);
  const enough = d.active.length >= 2;

  const builderId = params.get("edit");
  const sheets = (
    <>
      <OutfitBuilderSheet
        open={s.status === "ready" && (params.has("new") || !!builderId)}
        outfitId={builderId}
        onClose={close}
      />
      <OutfitDetailSheet
        open={s.status === "ready" && params.has("outfit")}
        outfitId={params.get("outfit")}
        onClose={close}
        onEdit={(id) => open("edit", id)}
      />
    </>
  );

  const head = (
    <div className="page-head">
      <h1>Outfits</h1>
      <p className="muted">
        {all.length} {all.length === 1 ? "outfit" : "outfits"}
      </p>
      {enough && (
        <button type="button" className="btn primary" onClick={() => open("new", "1")}>
          Build an outfit
        </button>
      )}
    </div>
  );

  // One return with the sheets always last, so they never remount when the page switches branches.
  let body: React.ReactNode;
  if (s.status !== "ready") body = <LoadGate s={s} />;
  else if (!all.length)
    body = enough ? (
      <EmptyState
        title="No outfits yet"
        actions={
          <button type="button" className="btn primary" onClick={() => open("new", "1")}>
            Build an outfit
          </button>
        }
      >
        Pick pieces that go together and tag where you’d wear them. Today then suggests whichever outfit you’ve gone
        longest without.
      </EmptyState>
    ) : (
      <EmptyState
        title="No outfits yet"
        actions={
          <Link className="btn primary" href="/closet?add=1">
            Add clothes
          </Link>
        }
      >
        Add a few clothes first, then put them together here.
      </EmptyState>
    );
  else
    body = (
      <>
        <Chips
          label="Occasion"
          options={[{ id: "any" as const, label: "All" }, ...OCCASIONS]}
          value={occ}
          onChange={setOcc}
        />
        {list.length ? (
          <>
            <p className="muted small">Least recently worn first.</p>
            <ul className="outfit-grid" aria-label="Your outfits">
              {list.map((o) => {
                const pieces = outfitPieces(o, d.byId);
                const w = d.stats.outfits.get(o.id) ?? NO_WEAR;
                const name = outfitName(o, pieces);
                return (
                  <li key={o.id} className="ocard">
                    <button type="button" className="ocard-main" aria-label={name} onClick={() => open("outfit", o.id)}>
                      <Flatlay pieces={pieces} />
                      <span className="ocard-name">{name}</span>
                    </button>
                    <div className="ocard-meta">
                      <HangTag small>{lastWornText(w.last, d.today)}</HangTag>
                      {o.occasions.map((x) => (
                        <span key={x} className="pill">
                          {OCC_LABEL[x]}
                        </span>
                      ))}
                    </div>
                    <div className="row tight">
                      <button
                        type="button"
                        className="btn sm primary"
                        aria-label={`Wear ${name} today`}
                        onClick={() =>
                          void wear(o, o.occasions.includes(current) ? current : (o.occasions[0] ?? current), d.today)
                        }
                      >
                        Wear today
                      </button>
                      <button
                        type="button"
                        className="btn sm ghost"
                        aria-label={`Edit ${name}`}
                        onClick={() => open("edit", o.id)}
                      >
                        Edit
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </>
        ) : (
          <p className="muted">No outfits tagged for this occasion yet.</p>
        )}
      </>
    );

  return (
    <>
      {head}
      {body}
      {sheets}
    </>
  );
}

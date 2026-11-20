"use client";

import Link from "next/link";
import { useState, useSyncExternalStore } from "react";
import { EmptyState } from "@/components/EmptyState";
import { HangTag } from "@/components/HangTag";
import { LoadGate } from "@/components/Loading";
import { MoreIdeas } from "@/components/MoreIdeas";
import { OccasionPicker } from "@/components/OccasionPicker";
import { OutfitBuilderSheet, OutfitDetailSheet } from "@/components/OutfitSheets";
import { Flatlay } from "@/components/Piece";
import { useWearActions } from "@/components/useWearActions";
import { useCloset, useDerived } from "@/lib/closet/store";
import type { Item, WearLog } from "@/lib/closet/types";
import { addDays, lastWornText, shortDate } from "@/lib/domain/dates";
import { orderPieces, outfitName, outfitPieces } from "@/lib/domain/outfit";
import { rotationFor } from "@/lib/domain/rotation";
import { NO_WEAR, sortLogsNewest } from "@/lib/domain/wear";
import { type Occasion, OCCASIONS } from "@/lib/occasions";
import { useOccasion } from "@/lib/use-occasion";
import { useSheetParam } from "@/lib/use-sheet-param";
import { useWeather } from "@/lib/use-weather";
import { weatherLine } from "@/lib/weather";

const OCC_LABEL = Object.fromEntries(OCCASIONS.map((o) => [o.id, o.label])) as Record<Occasion, string>;
const noSubscribe = () => () => {};
const dateLineNow = () => new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

export function TodayView() {
  const s = useCloset();
  const d = useDerived(s);
  const [occ] = useOccasion();
  const { wear, unwear } = useWearActions();
  const { params, open, close } = useSheetParam();
  const [pick, setPick] = useState({ occ, index: 0, showPicks: false });
  if (pick.occ !== occ) setPick({ occ, index: 0, showPicks: false }); // reset when the occasion changes
  const dateLine = useSyncExternalStore(noSubscribe, dateLineNow, () => "");
  const weather = useWeather(s.profile, d.today);

  const logName = (l: WearLog) => {
    const o = l.outfit_id ? s.outfits.find((x) => x.id === l.outfit_id) : undefined;
    const pieces = orderPieces(l.itemIds.map((id) => d.byId.get(id)).filter((x): x is Item => !!x));
    return o ? outfitName(o, outfitPieces(o, d.byId)) : pieces.map((p) => p.name).join(" + ") || "Outfit";
  };

  let main: React.ReactNode;
  if (s.status !== "ready") main = <LoadGate s={s} />;
  else if (!d.active.length)
    main = (
      <EmptyState
        title="Your closet is empty"
        actions={
          <Link className="btn primary" href="/closet?add=1">
            Add clothes
          </Link>
        }
      >
        Add the pieces you wear most: go-to shirts, trousers and shoes. Outfit picks start once there’s something to
        pick from.
      </EmptyState>
    );
  else {
    const logs = sortLogsNewest(s.logs);
    const done = logs.find((l) => l.worn_on === d.today && l.occasion === occ);
    const list = rotationFor(occ, s.outfits, d.byId, d.stats);
    const yesterday = addDays(d.today, -1);

    let card: React.ReactNode;
    if (done && !pick.showPicks) {
      const pieces = orderPieces(done.itemIds.map((id) => d.byId.get(id)).filter((x): x is Item => !!x));
      card = (
        <section className="pick" aria-label="Today’s outfit">
          <p className="kicker">You’re wearing</p>
          <h2 className="pick-name">{logName(done)}</h2>
          <Flatlay pieces={pieces} />
          <div className="row">
            <button type="button" className="btn" onClick={() => setPick({ occ, index: 0, showPicks: true })}>
              Pick something else
            </button>
            <button type="button" className="btn ghost" onClick={() => void unwear(done.id)}>
              Remove from log
            </button>
          </div>
        </section>
      );
    } else if (!list.length) {
      card = (
        <section className="pick empty-pick">
          <h2 className="pick-name">No {OCC_LABEL[occ].toLowerCase()} outfits saved yet</h2>
          <p className="muted">Put one together from your closet.</p>
          <div className="row">
            {d.active.length >= 2 ? (
              <button type="button" className="btn primary" onClick={() => open("new", "1")}>
                Build an outfit
              </button>
            ) : (
              <Link className="btn primary" href="/closet?add=1">
                Add clothes
              </Link>
            )}
          </div>
        </section>
      );
    } else {
      const i = pick.index % list.length;
      const o = list[i]!;
      const pieces = outfitPieces(o, d.byId);
      const w = d.stats.outfits.get(o.id) ?? NO_WEAR;
      card = (
        <section className="pick" aria-label="Suggested outfit">
          <p className="kicker">{i === 0 ? "Least recently worn" : `Option ${i + 1} of ${list.length}`}</p>
          <h2 className="pick-name">{outfitName(o, pieces)}</h2>
          <Flatlay pieces={pieces} />
          <div className="pick-meta">
            <HangTag>{lastWornText(w.last, d.today)}</HangTag>
            {w.count > 0 && (
              <span className="muted">
                {w.count} {w.count === 1 ? "wear" : "wears"} so far
              </span>
            )}
          </div>
          <div className="row">
            <button
              type="button"
              className="btn primary"
              onClick={async () => {
                const r = await wear(o, occ, d.today);
                if (r?.status === "logged") setPick({ occ, index: 0, showPicks: false });
              }}
            >
              Wear this
            </button>
            {list.length > 1 && (
              <button type="button" className="btn" onClick={() => setPick((p) => ({ ...p, index: p.index + 1 }))}>
                Next option
              </button>
            )}
            <button type="button" className="btn ghost" onClick={() => open("outfit", o.id)}>
              Details
            </button>
          </div>
        </section>
      );
    }

    const recent = logs.slice(0, 6);
    main = (
      <>
        {card}
        <MoreIdeas occasion={occ} weather={weather} />
        {recent.length > 0 && (
          <section className="block" aria-labelledby="recent-h">
            <div className="block-head">
              <h2 id="recent-h">Recently worn</h2>
            </div>
            <ul className="log">
              {recent.map((l) => (
                <li key={l.id}>
                  <span className="log-date">{l.worn_on === d.today ? "Today" : shortDate(l.worn_on, d.today)}</span>
                  <span className="log-name">{logName(l)}</span>
                  <span className="pill">{OCC_LABEL[l.occasion]}</span>
                  {l.worn_on === d.today || l.worn_on === yesterday ? (
                    <button type="button" className="link" onClick={() => void unwear(l.id)}>
                      Remove
                    </button>
                  ) : (
                    <span />
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}
      </>
    );
  }

  return (
    <div className="today">
      <section className="hero">
        <h1 className="sr">Today</h1>
        <p className="dateline">{dateLine || " "}</p>
        {weather && (
          <p className="dateline" data-testid="weather-line">
            {weatherLine(weather)}
          </p>
        )}
        <OccasionPicker />
      </section>
      <div className="today-main">{main}</div>
      <OutfitBuilderSheet
        open={s.status === "ready" && (params.has("new") || params.has("edit"))}
        outfitId={params.get("edit")}
        onClose={close}
      />
      <OutfitDetailSheet
        open={s.status === "ready" && params.has("outfit")}
        outfitId={params.get("outfit")}
        onClose={close}
        onEdit={(id) => open("edit", id)}
      />
    </div>
  );
}

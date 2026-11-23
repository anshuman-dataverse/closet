"use client";

import { useMemo, useState } from "react";
import { Chips } from "@/components/Chips";
import { EmptyState } from "@/components/EmptyState";
import { ItemSheet } from "@/components/ItemSheet";
import { LoadGate } from "@/components/Loading";
import { Sheet } from "@/components/Sheet";
import { PieceCell } from "@/components/Piece";
import { useToast } from "@/components/Toast";
import { setItemsStatus, useCloset, useDerived } from "@/lib/closet/store";
import { CATEGORIES, type Category, type ItemStatus } from "@/lib/closet/types";
import { shortDate } from "@/lib/domain/dates";
import { NO_WEAR } from "@/lib/domain/wear";
import { type Occasion, OCCASIONS } from "@/lib/occasions";
import { useSheetParam } from "@/lib/use-sheet-param";

const SORTS = [
  ["recent", "Recently added"],
  ["stale", "Longest since worn"],
  ["least", "Least worn"],
  ["most", "Most worn"],
  ["price", "Price, high to low"],
] as const;
type Sort = (typeof SORTS)[number][0];

const STATUSES: { id: ItemStatus; label: string }[] = [
  { id: "active", label: "Active" },
  { id: "laundry", label: "In laundry" },
  { id: "retired", label: "Retired" },
];

export function ClosetView() {
  const s = useCloset();
  const d = useDerived(s);
  const toast = useToast();
  const { params, open, close } = useSheetParam();
  const [cat, setCat] = useState<Category | "all">("all");
  const [occ, setOcc] = useState<Occasion | "any">("any");
  const [status, setStatus] = useState<ItemStatus>("active");
  const [sort, setSort] = useState<Sort>("recent");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const changed = (occ !== "any" ? 1 : 0) + (status !== "active" ? 1 : 0) + (sort !== "recent" ? 1 : 0);
  const reset = () => {
    setOcc("any");
    setStatus("active");
    setSort("recent");
  };

  const itemParam = params.get("item");
  const sheetOpen = params.has("add") || !!itemParam;

  const counts = useMemo(() => {
    const c = { active: 0, laundry: 0, retired: 0 } as Record<ItemStatus, number>;
    for (const i of s.items) c[i.status] += 1;
    return c;
  }, [s.items]);

  const list = useMemo(() => {
    const w = (id: string) => d.stats.items.get(id) ?? NO_WEAR;
    const l = s.items
      .filter((i) => i.status === status)
      .filter((i) => cat === "all" || i.category === cat)
      .filter((i) => occ === "any" || i.occasions.includes(occ));
    const by: Record<Sort, (a: (typeof l)[0], b: (typeof l)[0]) => number> = {
      recent: (a, b) => b.created_at.localeCompare(a.created_at),
      stale: (a, b) =>
        (w(a.id).last ?? "").localeCompare(w(b.id).last ?? "") || b.created_at.localeCompare(a.created_at),
      least: (a, b) => w(a.id).count - w(b.id).count,
      most: (a, b) => w(b.id).count - w(a.id).count,
      price: (a, b) => (b.price_cents ?? -1) - (a.price_cents ?? -1),
    };
    return [...l].sort(by[sort]);
  }, [s.items, d.stats, cat, occ, status, sort]);

  const laundryDone = async () => {
    const ids = s.items.filter((i) => i.status === "laundry").map((i) => i.id);
    try {
      await setItemsStatus(ids, "active");
      toast(`${ids.length} ${ids.length === 1 ? "piece is" : "pieces are"} back in your closet`, {
        action: "Undo",
        onAction: () => void setItemsStatus(ids, "laundry"),
      });
    } catch (e) {
      toast((e as Error).message);
    }
  };

  const head = (
    <div className="page-head">
      <h1>Closet</h1>
      <p className="muted">
        {counts.active + counts.laundry} {counts.active + counts.laundry === 1 ? "piece" : "pieces"}
      </p>
      <button type="button" className="btn primary" onClick={() => open("add", "1")} disabled={s.status !== "ready"}>
        Add clothes
      </button>
    </div>
  );

  const sheet = <ItemSheet open={sheetOpen && s.status === "ready"} itemId={itemParam} onClose={close} />;

  // One return with the sheet always last: switching between the empty state and the grid
  // (e.g. when a draft piece is saved) must not remount the sheet and lose its state.
  let body: React.ReactNode;
  if (s.status !== "ready") body = <LoadGate s={s} />;
  else if (!s.items.length)
    body = (
      <EmptyState
        title="Nothing here yet"
        actions={
          <button type="button" className="btn primary" onClick={() => open("add", "1")}>
            Add your first piece
          </button>
        }
      >
        Snap a photo of each piece you own. Fill in a name and where you’d wear it, and it’s in. Your Mac fills in the
        details for you once photo reading is on.
      </EmptyState>
    );
  else
    body = (
      <>
        <div className="filters">
          <div className="filter-row">
            <Chips
              label="Category"
              options={[{ id: "all" as const, label: "All" }, ...CATEGORIES.map((c) => ({ id: c, label: c }))]}
              value={cat}
              onChange={setCat}
            />
            <button
              type="button"
              className="btn sm filter-btn"
              aria-haspopup="dialog"
              onClick={() => setFiltersOpen(true)}
            >
              {changed ? `Filters · ${changed}` : "Filters"}
            </button>
          </div>
          {(changed > 0 || counts.laundry > 0) && (
            <div className="row tight">
              {changed > 0 && (
                <p className="muted small">
                  {[
                    occ !== "any" && OCCASIONS.find((o) => o.id === occ)?.label,
                    status !== "active" && STATUSES.find((x) => x.id === status)?.label,
                    sort !== "recent" && SORTS.find(([v]) => v === sort)?.[1],
                  ]
                    .filter(Boolean)
                    .join(" · ")}{" "}
                  <button type="button" className="link" onClick={reset}>
                    Clear
                  </button>
                </p>
              )}
              {counts.laundry > 0 && (
                <button type="button" className="btn sm" onClick={laundryDone}>
                  Laundry done ({counts.laundry})
                </button>
              )}
            </div>
          )}
        </div>
        {list.length ? (
          <ul className="grid" aria-label="Your pieces">
            {list.map((i) => {
              const w = d.stats.items.get(i.id) ?? NO_WEAR;
              const sub = w.count
                ? `${w.count} ${w.count === 1 ? "wear" : "wears"}, last ${shortDate(w.last, d.today)}`
                : "Not worn yet";
              return (
                <li key={i.id}>
                  <button type="button" className="tile" onClick={() => open("item", i.id)}>
                    <span className="tile-ph">
                      <PieceCell item={i} bare />
                    </span>
                    <span className="tile-name">
                      {i.name}
                      {i.is_sample && <span className="sample-tag">Sample</span>}
                    </span>
                    <span className="tile-sub">{sub}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="muted">Nothing matches these filters.</p>
        )}
      </>
    );

  const filters = (
    <Sheet
      open={filtersOpen}
      onClose={() => setFiltersOpen(false)}
      title="Filters"
      actions={
        <>
          <button type="button" className="btn" onClick={reset} disabled={!changed}>
            Reset
          </button>
          <span className="grow" />
          <button type="button" className="btn primary" onClick={() => setFiltersOpen(false)}>
            Show {list.length} {list.length === 1 ? "piece" : "pieces"}
          </button>
        </>
      }
    >
      <fieldset className="field">
        <legend>Occasion</legend>
        <Chips
          label="Occasion"
          wrap
          options={[{ id: "any" as const, label: "Any occasion" }, ...OCCASIONS]}
          value={occ}
          onChange={setOcc}
        />
      </fieldset>
      <fieldset className="field">
        <legend>Status</legend>
        <Chips
          label="Status"
          wrap
          options={STATUSES.map((x) => ({
            ...x,
            label: counts[x.id] && x.id !== "active" ? `${x.label} (${counts[x.id]})` : x.label,
          }))}
          value={status}
          onChange={setStatus}
        />
      </fieldset>
      <label className="field">
        <span>Sort</span>
        <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
          {SORTS.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </label>
    </Sheet>
  );

  return (
    <>
      {head}
      {body}
      {filters}
      {sheet}
    </>
  );
}

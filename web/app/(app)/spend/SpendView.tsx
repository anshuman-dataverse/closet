"use client";

import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { LoadGate } from "@/components/Loading";
import { PieceCell } from "@/components/Piece";
import { useCloset, useDerived } from "@/lib/closet/store";
import type { Item } from "@/lib/closet/types";
import { monthName } from "@/lib/domain/dates";
import { formatCents } from "@/lib/domain/money";
import { costPerWear } from "@/lib/domain/wear";
import { spendSummary } from "@/lib/domain/spend";

function MonthChart({ months, current }: { months: { month: string; cents: number }[]; current: string }) {
  const W = 360, base = 118, top = 12, bw = 18, gap = (W - 12 * bw) / 12; // prettier-ignore
  const max = Math.max(1, ...months.map((m) => m.cents));
  return (
    <svg
      className="chart"
      viewBox={`0 0 ${W} ${base + 26}`}
      role="img"
      aria-label="Clothing spend per month for the last 12 months"
    >
      {months.map((m, k) => {
        const h = m.cents ? Math.max(3, Math.round((m.cents / max) * (base - top))) : 2;
        const x = gap / 2 + k * (bw + gap);
        return (
          <g key={m.month}>
            <title>{`${monthName(m.month, true)}: ${formatCents(m.cents)}`}</title>
            <rect
              className={`bar${m.month === current ? " now" : ""}`}
              x={x.toFixed(1)}
              y={base - h}
              width={bw}
              height={h}
              rx={2}
            />
            <text className="axis" x={(x + bw / 2).toFixed(1)} y={base + 18} textAnchor="middle">
              {monthName(m.month).slice(0, 1)}
            </text>
          </g>
        );
      })}
      <line className="base" x1={0} x2={W} y1={base + 0.5} y2={base + 0.5} />
    </svg>
  );
}

function CpwList({ title, sub, rows }: { title: string; sub: string; rows: { item: Item; value: string }[] }) {
  const id = `${title.toLowerCase().replace(/[^a-z]+/g, "-")}-h`; // ids can't contain spaces
  return (
    <section className="block" aria-labelledby={id}>
      <div className="block-head">
        <h2 id={id}>{title}</h2>
      </div>
      <p className="muted small" style={{ margin: 0 }}>
        {sub}
      </p>
      <ul className="cpw">
        {rows.map((r) => (
          <li key={r.item.id}>
            <span className="tile-ph">
              <PieceCell item={r.item} bare />
            </span>
            <Link className="link" href={`/closet?item=${r.item.id}`}>
              {r.item.name}
            </Link>
            <span className="cpw-n">{r.value}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function SpendView() {
  const s = useCloset();
  const d = useDerived(s);
  const head = (
    <div className="page-head">
      <h1>Spend</h1>
    </div>
  );
  if (s.status !== "ready")
    return (
      <>
        {head}
        <LoadGate s={s} />
      </>
    );
  const budget = s.profile?.monthly_budget_cents ?? 0;
  const sum = spendSummary(s.items, d.stats, d.today, budget);
  if (!sum.hasPrices)
    return (
      <>
        {head}
        <EmptyState
          title="No prices yet"
          actions={
            <Link className="btn primary" href="/closet?add=1">
              Add clothes
            </Link>
          }
        >
          Add what you paid when you add clothes. This page then shows what you spend each month and which pieces earn
          their keep.
        </EmptyState>
      </>
    );

  const pct = budget ? Math.min(100, Math.round((sum.monthCents / budget) * 100)) : 0;
  const topCat = Math.max(1, ...sum.byCategory.map((c) => c.cents));
  return (
    <>
      {head}
      <section className="block" style={{ marginTop: 8 }} aria-label="This month">
        <p className="spend-num" data-testid="month-total">
          {formatCents(sum.monthCents)}
        </p>
        <p className="muted" style={{ margin: 0 }}>
          spent in {monthName(sum.month)}
          {budget ? ` of your ${formatCents(budget)} budget` : ""}
        </p>
        {budget ? (
          <>
            <div
              className={`meter${sum.over ? " over" : ""}`}
              role="meter"
              aria-label="Budget used"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={pct}
            >
              <span style={{ width: `${pct}%` }} />
            </div>
            <p className={`small ${sum.over ? "err" : "muted"}`} style={{ margin: 0 }} data-testid="budget-line">
              {sum.over
                ? `${formatCents(sum.monthCents - budget)} over budget`
                : `${formatCents(budget - sum.monthCents)} left this month`}
            </p>
          </>
        ) : (
          <div className="row">
            <Link className="link" href="/profile#settings">
              Set a monthly budget
            </Link>
          </div>
        )}
      </section>

      <section className="block" aria-labelledby="year-h">
        <div className="block-head">
          <h2 id="year-h">Last 12 months</h2>
          <span className="muted" data-testid="year-total">
            {formatCents(sum.yearCents)} total
          </span>
        </div>
        <MonthChart months={sum.months} current={sum.month} />
      </section>

      {sum.byCategory.length > 0 && (
        <section className="block" aria-labelledby="cat-h">
          <div className="block-head">
            <h2 id="cat-h">By category</h2>
          </div>
          <ul className="bars">
            {sum.byCategory.map((c) => (
              <li key={c.category}>
                <span>{c.category}</span>
                <span className="muted">{formatCents(c.cents)}</span>
                <div className="meter" aria-hidden="true">
                  <span style={{ width: `${Math.round((c.cents / topCat) * 100)}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {sum.earning.length > 0 && (
        <CpwList
          title="Earning their keep"
          sub="Lowest cost per wear so far."
          rows={sum.earning.map((r) => ({ item: r.item, value: `${formatCents(r.cpw)} per wear` }))}
        />
      )}
      {sum.waiting.length > 0 && (
        <CpwList
          title="Waiting for a wear"
          sub="Worn once or never, and bought more than a month ago."
          rows={sum.waiting.map((r) => ({
            item: r.item,
            value: r.wears
              ? `${formatCents(costPerWear(r.item.price_cents, r.wears))} per wear`
              : formatCents(r.item.price_cents),
          }))}
        />
      )}
      {sum.missingCount > 0 && (
        <p className="muted small">
          {sum.missingCount} {sum.missingCount === 1 ? "piece has" : "pieces have"} no price or purchase date, so{" "}
          {sum.missingCount === 1 ? "it isn’t" : "they aren’t"} in the monthly totals.
        </p>
      )}
    </>
  );
}

// Spend page numbers (SPEC 4.5). Uses bought_on (a local calendar day) and price_cents.
import type { Item } from "@/lib/closet/types";
import { daysBetween, isYmd, lastMonths } from "./dates";
import { costPerWear, NO_WEAR, type WearStats } from "./wear";

export type SpendSummary = {
  month: string;
  monthCents: number;
  budgetCents: number;
  over: boolean;
  months: { month: string; cents: number }[];
  yearCents: number;
  byCategory: { category: string; cents: number }[];
  earning: { item: Item; cpw: number; wears: number }[];
  waiting: { item: Item; wears: number }[];
  missingCount: number;
  hasPrices: boolean;
};

export function spendSummary(
  items: readonly Item[],
  stats: WearStats,
  today: string,
  budgetCents: number,
): SpendSummary {
  const priced = items.filter((i) => (i.price_cents ?? 0) > 0);
  const dated = priced.filter((i) => isYmd(i.bought_on));
  const months = lastMonths(today, 12);
  const byMonth = new Map(months.map((m) => [m, 0]));
  const cat = new Map<string, number>();
  for (const i of dated) {
    const m = i.bought_on!.slice(0, 7);
    if (!byMonth.has(m)) continue;
    byMonth.set(m, (byMonth.get(m) ?? 0) + i.price_cents!);
    const c = i.category ?? "Other";
    cat.set(c, (cat.get(c) ?? 0) + i.price_cents!);
  }
  const month = today.slice(0, 7);
  const monthCents = byMonth.get(month) ?? 0;
  const wears = (i: Item) => (stats.items.get(i.id) ?? NO_WEAR).count;

  const earning = priced
    .map((item) => ({ item, wears: wears(item), cpw: costPerWear(item.price_cents, wears(item)) ?? 0 }))
    .filter((r) => r.wears >= 2)
    .sort((a, b) => a.cpw - b.cpw)
    .slice(0, 5);

  const waiting = priced
    .filter((i) => i.status !== "retired" && wears(i) <= 1)
    .filter((i) => !isYmd(i.bought_on) || daysBetween(i.bought_on, today) >= 30)
    .sort((a, b) => (b.price_cents ?? 0) - (a.price_cents ?? 0))
    .slice(0, 5)
    .map((item) => ({ item, wears: wears(item) }));

  return {
    month,
    monthCents,
    budgetCents,
    over: budgetCents > 0 && monthCents > budgetCents,
    months: months.map((m) => ({ month: m, cents: byMonth.get(m) ?? 0 })),
    yearCents: [...byMonth.values()].reduce((a, b) => a + b, 0),
    byCategory: [...cat].map(([category, cents]) => ({ category, cents })).sort((a, b) => b.cents - a.cents),
    earning,
    waiting,
    missingCount: items.filter((i) => i.status !== "retired" && !((i.price_cents ?? 0) > 0 && isYmd(i.bought_on)))
      .length,
    hasPrices: priced.length > 0,
  };
}

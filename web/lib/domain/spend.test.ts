import { describe, expect, it } from "vitest";
import { item, log } from "./fixtures";
import { spendSummary } from "./spend";
import { wearStats } from "./wear";

const today = "2026-11-20";
const items = [
  item({ id: "a", category: "Tops", price_cents: 3950, bought_on: "2026-11-14" }),
  item({ id: "b", category: "Shoes", price_cents: 12000, bought_on: "2026-11-02" }),
  item({ id: "c", category: "Tops", price_cents: 3200, bought_on: "2026-09-11" }),
  item({ id: "d", category: "Bottoms", price_cents: 6000, bought_on: "2025-05-01" }), // older than 12 months
  item({ id: "e", category: "Layers", price_cents: 9000 }), // no date
  item({ id: "f", category: "Layers" }), // no price
  item({ id: "g", category: "Tops", price_cents: 100000, bought_on: "2026-08-01", status: "retired" }),
];
const stats = wearStats([
  log({ worn_on: "2026-11-15", itemIds: ["a", "c"] }),
  log({ worn_on: "2026-11-16", itemIds: ["a", "c"] }),
  log({ worn_on: "2026-11-17", itemIds: ["c"] }),
  log({ worn_on: "2026-11-18", itemIds: ["b"] }),
]);
const s = spendSummary(items, stats, today, 15000);

describe("spendSummary", () => {
  it("this month and budget", () => {
    expect(s.monthCents).toBe(15950);
    expect(s.over).toBe(true);
  });
  it("12 months, current last, older purchases excluded", () => {
    expect(s.months).toHaveLength(12);
    expect(s.months[11]).toEqual({ month: "2026-11", cents: 15950 });
    expect(s.yearCents).toBe(15950 + 3200 + 100000);
  });
  it("by category, biggest first", () => {
    expect(s.byCategory[0]).toEqual({ category: "Tops", cents: 3950 + 3200 + 100000 });
  });
  it("earning their keep: 2+ wears, lowest cost per wear", () => {
    expect(s.earning.map((r) => [r.item.id, r.cpw])).toEqual([
      ["c", 1067],
      ["a", 1975],
    ]);
  });
  it("waiting for a wear: ≤1 wear, 30+ days old or undated, not retired, priciest first", () => {
    expect(s.waiting.map((r) => r.item.id)).toEqual(["e", "d"]);
  });
  it("counts active pieces missing a price or date", () => expect(s.missingCount).toBe(2));
});

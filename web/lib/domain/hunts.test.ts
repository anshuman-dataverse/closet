import { describe, expect, it } from "vitest";
import type { Wish } from "@/lib/closet/types";
import {
  foundBySlot,
  type Hunt,
  huntStatus,
  lookSets,
  normalizeBudget,
  percentOff,
  priceDrop,
  sizeNote,
} from "./hunts";

const hunt = (p: Partial<Hunt>): Hunt => ({ status: "done", error: null, results: [], ...p }) as Hunt;
const wish = (p: Partial<Wish>): Wish =>
  ({
    watch: true,
    status: "wanted",
    price_cents: 5000,
    target_price_cents: null,
    last_seen_price_cents: null,
    ...p,
  }) as Wish;

describe("hunts", () => {
  it("swaps reversed budgets", () => {
    expect(normalizeBudget(6000, 2500)).toEqual({ min: 2500, max: 6000 });
    expect(normalizeBudget(null, 4000)).toEqual({ min: null, max: 4000 });
  });
  it("status lines", () => {
    expect(huntStatus(hunt({ status: "queued" }), true)).toBe("Waiting for your Mac");
    expect(huntStatus(hunt({ status: "queued" }), false)).toBe("Queued");
    expect(huntStatus(hunt({ status: "running" }), false)).toBe("Searching…");
    expect(huntStatus(hunt({ status: "failed", error: "SearXNG isn’t reachable" }), false)).toBe(
      "Failed: SearXNG isn’t reachable",
    );
    expect(huntStatus(hunt({ results: [{} as never] }), false)).toBe("1 pick");
    expect(huntStatus(hunt({}), false)).toBe("0 picks");
    expect(
      huntStatus(hunt({ kind: "look", results: [{ set_no: 1 }, { set_no: 1 }, { set_no: 2 }] as never }), false),
    ).toBe("2 looks");
    expect(huntStatus(hunt({ kind: "look", results: [{ set_no: null }] as never }), false)).toBe("No complete look");
  });
  it("percent off and sizes", () => {
    expect(percentOff(3900, 5500)).toBe(29);
    expect(percentOff(3900, 3900)).toBeNull();
    expect(percentOff(null, 5000)).toBeNull();
    expect(sizeNote("yes")).toBe("Your size is in stock");
    expect(sizeNote("unknown")).toBe("Size: check the store");
  });
});

describe("priceDrop", () => {
  it("flags a target hit or a 15% fall, only from checked prices", () => {
    expect(priceDrop(wish({ last_seen_price_cents: null }))).toBeNull(); // never checked
    expect(priceDrop(wish({ last_seen_price_cents: 4300 }))).toBeNull(); // 14% down
    expect(priceDrop(wish({ last_seen_price_cents: 4250 }))).toEqual({ from: 5000, to: 4250 }); // 15%
    expect(priceDrop(wish({ last_seen_price_cents: 4800, target_price_cents: 4800 }))).toEqual({
      from: 5000,
      to: 4800,
    });
    expect(priceDrop(wish({ last_seen_price_cents: 1000, watch: false }))).toBeNull();
    expect(priceDrop(wish({ last_seen_price_cents: 1000, status: "bought" }))).toBeNull();
  });
});

describe("looks", () => {
  const r = (p: Record<string, unknown>) =>
    ({ owned_item_id: null, url: "https://x", price_cents: 1000, ...p }) as never;
  it("groups sets in slot order and totals what to buy", () => {
    const sets = lookSets([
      r({ set_no: 2, rank: 5, slot: "Top", price_cents: 3000 }),
      r({ set_no: 1, rank: 2, slot: "Shoes", price_cents: 5000 }),
      r({ set_no: 1, rank: 1, slot: "Top", price_cents: 2300 }),
      r({ set_no: 1, rank: 3, slot: "Bottoms", owned_item_id: "mine", url: null, price_cents: null }),
    ]);
    expect(sets.map((s) => s.no)).toEqual([1, 2]);
    expect(sets[0]!.pieces.map((p) => (p as { slot: string }).slot)).toEqual(["Top", "Shoes", "Bottoms"]);
    expect(sets[0]!.total).toBe(7300); // the owned chinos cost nothing
    expect(sets[0]!.toBuy).toHaveLength(2);
  });
  it("lists found pieces by slot when nothing is complete", () => {
    const f = foundBySlot([
      r({ set_no: null, slot: "Top", rank: 1 }),
      r({ set_no: null, slot: "Top", rank: 2 }),
      r({ set_no: 1, slot: "Top", rank: 3 }),
    ]);
    expect(f.map(([slot, rs]) => [slot, rs.length])).toEqual([["Top", 2]]);
  });
});

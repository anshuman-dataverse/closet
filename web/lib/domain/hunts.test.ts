import { describe, expect, it } from "vitest";
import type { Wish } from "@/lib/closet/types";
import { type Hunt, huntStatus, normalizeBudget, percentOff, priceDrop, sizeNote } from "./hunts";

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

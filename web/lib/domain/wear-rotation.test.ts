import { describe, expect, it } from "vitest";
import { item, log, outfit } from "./fixtures";
import { outfitName, orderPieces, validateOutfit } from "./outfit";
import { leastRecentlyWorn, rotationFor } from "./rotation";
import { costPerWear, wearStats } from "./wear";

const shirt = item({ id: "shirt", name: "Navy oxford", category: "Tops" });
const chinos = item({ id: "chinos", name: "Grey chinos", category: "Bottoms" });
const boots = item({ id: "boots", name: "Boots", category: "Shoes" });
const sweater = item({ id: "sweater", name: "Sweater", category: "Layers", status: "laundry" });
const old = item({ id: "old", name: "Old tee", category: "Tops", status: "retired" });
const byId = new Map([shirt, chinos, boots, sweater, old].map((i) => [i.id, i]));

describe("wearStats", () => {
  const logs = [
    log({ worn_on: "2026-11-10", outfit_id: "a", itemIds: ["shirt", "chinos"] }),
    log({ worn_on: "2026-11-15", outfit_id: "a", itemIds: ["shirt", "chinos"] }),
    log({ worn_on: "2026-11-12", itemIds: ["shirt", "shirt"] }),
  ];
  const s = wearStats(logs);
  it("counts pieces from the snapshot, once per log", () => {
    expect(s.items.get("shirt")).toEqual({ count: 3, last: "2026-11-15" });
    expect(s.items.get("chinos")).toEqual({ count: 2, last: "2026-11-15" });
  });
  it("counts outfits from wear_logs", () => expect(s.outfits.get("a")).toEqual({ count: 2, last: "2026-11-15" }));
  it("cost per wear never divides by zero", () => {
    expect(costPerWear(4000, 0)).toBe(4000);
    expect(costPerWear(4000, 3)).toBe(1333);
    expect(costPerWear(null, 3)).toBeNull();
  });
});

describe("rotationFor", () => {
  const a = outfit({ id: "a", itemIds: ["shirt", "chinos"], created_at: "2026-01-01T00:00:00Z" });
  const b = outfit({ id: "b", itemIds: ["shirt", "boots"], created_at: "2026-01-02T00:00:00Z" });
  const c = outfit({ id: "c", itemIds: ["chinos", "boots"], created_at: "2026-01-03T00:00:00Z" });
  const never = outfit({ id: "n", itemIds: ["chinos", "shirt"], created_at: "2026-01-04T00:00:00Z" });
  const laundry = outfit({ id: "l", itemIds: ["shirt", "sweater"] });
  const retired = outfit({ id: "r", itemIds: ["old", "chinos"] });
  const party = outfit({ id: "p", itemIds: ["shirt", "chinos"], occasions: ["party"] });
  const stats = wearStats([
    log({ worn_on: "2026-11-18", outfit_id: "a", itemIds: [] }),
    log({ worn_on: "2026-11-02", outfit_id: "b", itemIds: [] }),
    log({ worn_on: "2026-11-02", outfit_id: "c", itemIds: [] }),
  ]);
  const order = rotationFor("office", [a, b, c, never, laundry, retired, party], byId, stats).map((o) => o.id);
  it("never-worn first, then oldest last-worn, ties by created_at", () => expect(order).toEqual(["n", "b", "c", "a"]));
  it("skips laundry, retired and other occasions", () => {
    expect(order).not.toContain("l");
    expect(order).not.toContain("r");
    expect(order).not.toContain("p");
  });
  it("outfits page: least recently worn first", () => {
    expect(leastRecentlyWorn([a, b, never], stats).map((o) => o.id)).toEqual(["n", "b", "a"]);
  });
});

describe("outfit helpers", () => {
  it("orders pieces Tops, Sets, Layers, Bottoms, Shoes, Accessories", () => {
    const belt = item({ id: "belt", category: "Accessories" });
    expect(orderPieces([belt, boots, chinos, sweater, shirt]).map((i) => i.id)).toEqual([
      "shirt",
      "sweater",
      "chinos",
      "boots",
      "belt",
    ]);
  });
  it("default name joins the first two pieces", () => {
    expect(outfitName({ name: null }, [shirt, chinos, boots])).toBe("Navy oxford + Grey chinos");
    expect(outfitName({ name: "  Work " }, [shirt])).toBe("Work");
    expect(outfitName({ name: "" }, [])).toBe("Untitled outfit");
  });
  it("validation messages", () => {
    expect(validateOutfit(["a"], ["office"])).toMatch(/two pieces/);
    expect(validateOutfit(["a", "a"], ["office"])).toMatch(/two pieces/);
    expect(validateOutfit(["a", "b"], [])).toMatch(/occasion/);
    expect(validateOutfit(["a", "b"], ["office"])).toBeNull();
  });
});

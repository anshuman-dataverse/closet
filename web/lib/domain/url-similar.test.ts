import { describe, expect, it } from "vitest";
import { overlapNote, similarTo } from "./similar";
import { normalizeUrl, storeFromUrl } from "./url";

describe("normalizeUrl", () => {
  it("adds https and keeps http(s)", () => {
    expect(normalizeUrl("uniqlo.com/us/en/products/E123")).toBe("https://uniqlo.com/us/en/products/E123");
    expect(normalizeUrl("http://shop.test/x")).toBe("http://shop.test/x");
  });
  it("rejects other schemes and junk", () => {
    expect(normalizeUrl("javascript:alert(1)")).toBeNull();
    expect(normalizeUrl("ftp://x.com/a")).toBeNull();
    expect(normalizeUrl("not a link")).toBeNull();
    expect(normalizeUrl("")).toBeNull();
  });
  it("store name from link", () => expect(storeFromUrl("https://www.jcrew.com/p/1")).toBe("jcrew.com"));
});

describe("similarTo", () => {
  const owned = [
    { name: "Navy oxford shirt", type: "Oxford shirt", category: "Tops" as const, color_name: "Navy" },
    { name: "White oxford shirt", type: "Oxford shirt", category: "Tops" as const, color_name: "White" },
    { name: "White sneakers", type: "Sneakers", category: "Shoes" as const, color_name: "White" },
    { name: "Grey slim chinos", type: "Chinos", category: "Bottoms" as const, color_name: "Grey" },
    { name: "Old oxford", type: "Oxford shirt", category: "Tops" as const, color_name: "Blue", status: "retired" },
  ];
  it("same category and a shared meaningful word, color matches first", () => {
    const hits = similarTo({ name: "White oxford shirt (slim fit)", category: "Tops", color_name: "White" }, owned);
    expect(hits.map((h) => h.name)).toEqual(["White oxford shirt", "Navy oxford shirt"]);
  });
  it("ignores color and generic words", () => {
    expect(similarTo({ name: "Slim navy cotton tee", category: "Tops", color_name: "Navy" }, owned)).toEqual([]);
    expect(similarTo({ name: "Khaki chinos", category: "Bottoms" }, owned).map((h) => h.name)).toEqual([
      "Grey slim chinos",
    ]);
  });
  it("different category never matches", () => {
    expect(similarTo({ name: "White oxford shoes", category: "Shoes" }, owned)).toEqual([]);
  });
  it("note", () => {
    expect(overlapNote([{ name: "A" }, { name: "B" }, { name: "C" }])).toBe("You own 3 similar: A, B, C.");
    expect(overlapNote([])).toBe("");
  });
});

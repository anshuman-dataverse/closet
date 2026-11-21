import { describe, expect, it } from "vitest";
import { fitLabel, fitOptions, isWears, keepFit } from "./fit";

const ids = (c: Parameters<typeof fitOptions>[0], w: string | null) => fitOptions(c, w).map((f) => f.id);

describe("fit choices", () => {
  it("follow the category and what you wear", () => {
    expect(ids("Bottoms", "menswear")).toEqual(["skinny", "slim", "straight", "relaxed", "wide", "bootcut", "flare"]);
    expect(ids("Bottoms", "womenswear")).toContain("barrel");
    expect(ids("Tops", "menswear")).toEqual(["slim", "regular", "relaxed", "oversized"]);
    expect(ids("Layers", "womenswear")).toContain("cropped");
    expect(ids("Sets & suits", null)).toContain("a-line");
    expect(ids("Shoes", "menswear")).toEqual([]);
    expect(ids("Accessories", null)).toEqual([]);
  });
  it("labels and category changes", () => {
    expect(fitLabel("Bottoms", "wide")).toBe("Wide or baggy");
    expect(fitLabel("Tops", "cropped")).toBe("Cropped");
    expect(fitLabel("Tops", "")).toBe("");
    expect(keepFit("Layers", "oversized")).toBe("oversized");
    expect(keepFit("Shoes", "slim")).toBe("");
    expect(keepFit("Bottoms", "oversized")).toBe("");
    expect(isWears("both") && !isWears("kids")).toBe(true);
  });
});

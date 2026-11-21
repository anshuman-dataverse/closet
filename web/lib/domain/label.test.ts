import { describe, expect, it } from "vitest";
import { labelMessage, mergeLabel, parseLabel } from "./label";

const RAW = {
  brand: "Levi's",
  size: "W32 L30",
  fit: "relaxed",
  materials: [
    { fiber: "cotton", pct: 98 },
    { fiber: "elastane", pct: 2 },
  ],
  notes: [],
};
const blank = { category: "Bottoms" as const, brand: "", size: "", fit: "", notes: "" };

describe("label", () => {
  it("parses and drops junk", () => {
    expect(parseLabel(RAW)).toEqual({
      brand: "Levi's",
      size: "W32 L30",
      fit: "relaxed",
      materials: "98% cotton, 2% elastane",
      notes: [],
    });
    expect(parseLabel(null)).toBeNull();
    expect(parseLabel({ materials: [{ nope: 1 }], notes: [3] })).toMatchObject({ materials: "", notes: [] });
  });
  it("fills only empty, untouched fields", () => {
    const l = parseLabel(RAW)!;
    const { form, filled } = mergeLabel({ ...blank, brand: "My brand" }, new Set(["size"]), l);
    expect(form).toMatchObject({ brand: "My brand", size: "", fit: "relaxed", notes: "98% cotton, 2% elastane" });
    expect(filled).toEqual(["fit", "notes"]);
    expect(labelMessage(l, filled, "Bottoms")).toBe("Filled from the label: fit (Relaxed) and materials. Check them.");
  });
  it("drops a fit that isn't one for the category", () => {
    const l = parseLabel({ ...RAW, fit: "oversized" })!;
    expect(mergeLabel(blank, new Set(), l).form.fit).toBe(""); // oversized isn't a pants fit
  });
  it("explains when nothing was read", () => {
    const l = parseLabel({ notes: ["no text found: take the label straight on, close up, in good light"] })!;
    expect(labelMessage(l, [], "Tops")).toBe(
      "Couldn’t find any text on the label. Take it straight on, close up, in good light.",
    );
    const chart = parseLabel({ notes: ["more than one size printed (L, M), so none was picked"] })!;
    expect(labelMessage(chart, [], "Tops")).toBe("More than one size printed (L, M), so none was picked.");
    expect(labelMessage(parseLabel(RAW)!, [], "Bottoms")).toBe("Read the label. Your own details were kept.");
  });
});

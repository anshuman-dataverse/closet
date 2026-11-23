import { describe, expect, it } from "vitest";

import { cleanPicks, lookSlots, lookTypesText } from "./looks";

describe("looks", () => {
  it("lists real choices per slot and skips single-choice slots", () => {
    const office = lookSlots("office");
    expect(office.map((s) => s.label)).toEqual(["Top", "Layer", "Bottoms", "Shoes"]);
    expect(office[0]?.options.map((o) => o.id)).toContain("knit polo");
    expect(lookSlots("nowhere")).toEqual([]);
  });
  it("keeps only picks the occasion offers", () => {
    expect(cleanPicks("office", { Tops: "knit polo", Layers: "hoodie" })).toEqual({ Tops: "knit polo" });
    expect(cleanPicks("office", {})).toBeNull();
  });
  it("writes the types in slot order", () => {
    expect(lookTypesText({ Bottoms: "chinos", Tops: "knit polo", Shoes: "loafers" })).toBe(
      "Knit polo, chinos and loafers",
    );
    expect(lookTypesText(null)).toBe("");
  });
});

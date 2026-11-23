import { describe, expect, it } from "vitest";
import { fitOptions } from "./fit";
import { SAMPLES, sampleRows } from "./samples";

describe("samples", () => {
  it("cover every slot and use real colors and fits", () => {
    const cats = new Set(SAMPLES.map((x) => x.category));
    expect([...cats].sort()).toEqual(["Accessories", "Bottoms", "Layers", "Shoes", "Tops"]);
    for (const r of sampleRows()) {
      expect(r.is_sample).toBe(true);
      expect(r.color_hex, r.name).toMatch(/^#[0-9a-f]{6}$/);
      if (r.fit)
        expect(
          fitOptions(r.category, "menswear").map((f) => f.id),
          r.name,
        ).toContain(r.fit);
    }
  });
});

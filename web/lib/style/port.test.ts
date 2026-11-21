import { describe, expect, it } from "vitest";
import { fitNotes } from "./body";
import { hueDeg, itaDeg, srgbToLab } from "./color";
import { classifyFace } from "./face-shape";
import golden from "./golden.json";
import { contrast, depth, undertone } from "./skin";

// Golden values come from the Python worker (scripts/export-style-data.py): the port must match exactly.
describe("TypeScript port matches the Python worker", () => {
  it("sRGB → L*a*b*", () => {
    for (const g of golden.lab) {
      const lab = srgbToLab(g.rgb[0]!, g.rgb[1]!, g.rgb[2]!);
      lab.forEach((v, i) => expect(v).toBeCloseTo(g.lab[i]!, 3));
    }
  });
  it("undertone, depth, hue, ITA", () => {
    for (const g of golden.tones) {
      const lab = g.lab as [number, number, number];
      expect(undertone(lab)).toBe(g.undertone);
      expect(depth(lab)).toBe(g.depth);
      expect(hueDeg(lab)).toBeCloseTo(g.hue, 3);
      expect(itaDeg(lab)).toBeCloseTo(g.ita, 3);
    }
  });
  it("contrast", () => {
    for (const g of golden.contrast) expect(contrast(g.skin, g.hair)).toBe(g.out);
  });
  it("face shape", () => {
    for (const g of golden.faceShape) expect(classifyFace(g.ratios)).toBe(g.shape);
  });
  it("fit notes", () => {
    for (const g of golden.fitNotes) expect(fitNotes(g.ratios)).toEqual(g.notes);
  });
});

describe("palette builder matches the worker", () => {
  it("same text, swatches and notes for each override case", async () => {
    const { buildAnalysis } = await import("./build");
    for (const c of golden.build.cases) {
      const a = buildAnalysis(golden.build.measurements as never, c.overrides as never);
      for (const k of Object.keys(c.out) as (keyof typeof c.out)[]) expect(a[k], k).toEqual(c.out[k]);
    }
  });
});

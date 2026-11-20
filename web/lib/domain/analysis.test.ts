import { describe, expect, it } from "vitest";
import { canAnalyze, nextKind, parseAnalysis } from "./analysis";

const RAW = {
  computed: { undertone: "warm", depth: "medium", contrast: "high" },
  effective: { undertone: "cool", depth: "medium", contrast: "high" },
  summary: "Cool undertone…",
  best: [
    { name: "Navy", hex: "#1F2A48" },
    { name: "Bad", hex: "red" },
  ],
  neutrals: [{ name: "Grey", hex: "#8a8f98" }],
  careful: [{ name: "Orange", hex: "#d8722a", why: "Can clash." }],
  fit_notes: [{ area: "Shirts", advice: "Shoulder seam on the shoulder point." }, { area: "" }],
  occasion_tips: { office: "Navy layers.", junk: 3 },
  face: { shape: "round", why: "Angles add structure.", frames: ["Rectangular frames"], hair: ["Height on top"] },
  confidence_note: null,
  borderline: ["Your contrast read is close."],
};

describe("parseAnalysis", () => {
  it("keeps valid parts and drops junk", () => {
    const a = parseAnalysis(RAW)!;
    expect(a.best).toEqual([{ name: "Navy", hex: "#1f2a48" }]);
    expect(a.careful[0]!.why).toBe("Can clash.");
    expect(a.fit_notes).toHaveLength(1);
    expect(a.occasion_tips).toEqual({ office: "Navy layers." });
    expect(a.face.shape).toBe("round");
    expect(a.note).toBe("An estimate from your photos. You can change it.");
  });
  it("null without colors", () => {
    expect(parseAnalysis({ ...RAW, best: [] })).toBeNull();
    expect(parseAnalysis(null)).toBeNull();
  });
});

describe("photo kinds", () => {
  it("suggests the next useful kind", () => {
    expect(nextKind([])).toBe("face");
    expect(nextKind(["face"])).toBe("front");
    expect(nextKind(["face", "front", "side", "back"])).toBe("other");
  });
  it("needs a face and a front to analyze", () => {
    expect(canAnalyze(["face"])).toBe(false);
    expect(canAnalyze(["front", "face"])).toBe(true);
  });
});

import { describe, expect, it } from "vitest";
import { applyGains, findPaper, paperAt } from "./calibrate";
import { chroma, srgbToLab } from "./color";
import { combine, type FaceRead } from "./combine";
import { checkBody, checkFace } from "./quality";
import { readSkin } from "./skin";
import type { Pixels, Point } from "./types";

const W = 400,
  H = 500;
const SKIN: [number, number, number] = [200, 160, 130];

/** A synthetic face photo: skin block, dark hair, grey wall, optional white paper; optional color cast. */
function photo(
  opts: { paper?: boolean; cast?: [number, number, number]; skin?: [number, number, number] } = {},
): Pixels {
  const d = new Uint8ClampedArray(W * H * 4);
  const cast = opts.cast ?? [1, 1, 1];
  const skin = opts.skin ?? SKIN;
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      let c: [number, number, number] = [150, 150, 150];
      if (x >= 100 && x < 300 && y >= 150 && y < 430) c = skin;
      else if (x >= 110 && x < 290 && y >= 60 && y < 150) c = [35, 28, 24];
      else if (opts.paper && x >= 318 && x < 392 && y >= 180 && y < 440) c = [235, 235, 235];
      const i = (y * W + x) * 4;
      // apply the cast in linear light, like a real illuminant
      for (let k = 0; k < 3; k++) {
        const lin = (c[k]! / 255) ** 2.2 * cast[k]!;
        d[i + k] = Math.round(Math.min(1, lin) ** (1 / 2.2) * 255);
      }
      d[i + 3] = 255;
    }
  return { data: d, width: W, height: H };
}

export function fakeFace(w = W, h = H): Point[] {
  const p: Point[] = Array.from({ length: 478 }, () => [w / 2, h * 0.6]);
  const set = (i: number, x: number, y: number) => (p[i] = [x * w, y * h]);
  set(234, 0.25, 0.52);
  set(454, 0.75, 0.52);
  set(10, 0.5, 0.3);
  set(152, 0.5, 0.84);
  set(50, 0.375, 0.6);
  set(280, 0.625, 0.6);
  set(151, 0.5, 0.38);
  set(1, 0.5, 0.6);
  set(172, 0.2925, 0.75);
  set(397, 0.7075, 0.75);
  set(103, 0.285, 0.36);
  set(332, 0.715, 0.36);
  return p;
}
const FACE_BOX = { x0: 100, y0: 150, x1: 300, y1: 430 };

describe("white-paper calibration", () => {
  it("finds the paper and removes a warm cast", () => {
    const tinted = photo({ paper: true, cast: [1.0, 0.85, 0.6] });
    const { paper, problem } = findPaper(tinted, FACE_BOX);
    expect(problem).toBeNull();
    expect(paper!.cast).toBeGreaterThan(10);
    const fixed = applyGains(tinted, paper!.gains);
    const truth = readSkin(photo({ paper: true }), fakeFace()).lab;
    const raw = readSkin(tinted, fakeFace()).lab;
    const cal = readSkin(fixed, fakeFace()).lab;
    const dist = (a: number[], b: number[]) => Math.hypot(a[1]! - b[1]!, a[2]! - b[2]!);
    expect(dist(raw, truth)).toBeGreaterThan(8); // the cast shifts the read a lot…
    expect(dist(cal, truth)).toBeLessThan(2.5); // …calibration brings it back
    const i = (300 * W + 350) * 4;
    expect(chroma(srgbToLab(fixed.data[i]!, fixed.data[i + 1]!, fixed.data[i + 2]!))).toBeLessThan(2);
  });
  it("explains a missing paper, and tap-to-pick works", () => {
    expect(findPaper(photo(), FACE_BOX).problem).toMatch(/No white paper found/);
    const picked = paperAt(photo({ paper: true, cast: [1, 0.9, 0.7] }), 355, 300);
    expect(picked.paper).not.toBeNull();
    expect(paperAt(photo({ paper: true }), 200, 100).problem).toMatch(/too dark/);
  });
});

describe("photo checks", () => {
  it("one face, facing the camera, close enough", () => {
    const img = photo();
    expect(checkFace(img, []).problems[0]).toMatch(/No face found/);
    expect(checkFace(img, [fakeFace(), fakeFace()]).problems[0]).toMatch(/More than one face/);
    expect(checkFace(img, [fakeFace()]).ok).toBe(true);
    const turned = fakeFace();
    turned[1] = [W * 0.62, H * 0.6];
    expect(checkFace(img, [turned]).problems).toContain("Face the camera straight on, then retake.");
  });
  it("dark photos are rejected", () => {
    expect(checkFace(photo({ skin: [40, 30, 25] }), [fakeFace()]).problems.join(" ")).toMatch(/too dark/);
  });
  it("body photo needs shoulders, hips and ankles", () => {
    expect(checkBody([]).problems[0]).toMatch(/No person/);
    const lm = Array.from({ length: 33 }, () => [0, 0, 0.1] as [number, number, number]);
    expect(checkBody([lm]).problems[0]).toMatch(/shoulders, hips and ankles/);
  });
});

describe("combining photos", () => {
  const read = (lab: [number, number, number], calibrated: boolean): FaceRead => ({
    lab,
    hairL: 30,
    calibrated,
    lighting: null,
    ratios: { length: 1.3, jaw: 0.83, forehead: 0.86, yaw: 0.02 },
  });
  it("calibrated photos that agree give high confidence", () => {
    const c = combine([read([60, 12, 24], true), read([61, 12, 25], true)], null); // hue ≈ 63°, clear of cutoffs
    expect(c.confidence).toBe("high");
    expect(c.askSecond).toBe(false);
    expect(c.measurements.face_shape).toBe("oval");
  });
  it("one uncalibrated photo is low confidence and asks for another", () => {
    const c = combine([read([60, 12, 12.5], false)], null);
    expect(c.confidence).toBe("low");
    expect(c.askSecond).toBe(true);
    expect(c.reasons.join(" ")).toMatch(/Not calibrated/);
  });
  it("disagreement is reported", () => {
    const c = combine([read([60, 15, 10], true), read([60, 10, 22], true)], null);
    expect(c.reasons.join(" ")).toMatch(/disagree/);
    expect(c.askSecond).toBe(true);
  });
});

describe("paper detection ignores sky and walls", () => {
  it("a bright background touching the top edge is not paper", () => {
    const img = photo();
    for (let y = 0; y < 60; y++)
      // bright overcast sky band across the top
      for (let x = 0; x < W; x++) {
        const i = (y * W + x) * 4;
        img.data[i] = 225;
        img.data[i + 1] = 228;
        img.data[i + 2] = 232;
      }
    expect(findPaper(img, FACE_BOX).paper).toBeNull();
  });
});

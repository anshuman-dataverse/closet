// Combine reads from several photos into one measurement with an honest confidence level.
import { hueDeg, itaDeg, type Lab, median } from "./color";
import { T } from "./data";
import type { BodyRatios } from "./body";
import type { Measurements } from "./build";
import { classifyFace, type FaceRatios, voteShape } from "./face-shape";
import { undertone } from "./skin";

export type FaceRead = {
  lab: Lab;
  hairL: number | null;
  ratios: FaceRatios;
  calibrated: boolean;
  lighting: string | null;
};
export type Confidence = "high" | "medium" | "low";
export type Combined = { measurements: Measurements; confidence: Confidence; reasons: string[]; askSecond: boolean };

export function combine(reads: FaceRead[], body: BodyRatios | null): Combined {
  const good = reads.filter((r) => r.lighting === null).length ? reads.filter((r) => r.lighting === null) : reads;
  const lab: Lab = [0, 1, 2].map((i) => median(good.map((r) => r.lab[i]!))) as Lab;
  const hair = good.map((r) => r.hairL).filter((h): h is number => h !== null);
  const tones = good.map((r) => undertone(r.lab));
  const agree = new Set(tones).size === 1;
  const calibrated = good.filter((r) => r.calibrated).length;
  const hue = hueDeg(lab);
  const edge = T.borderline ?? 3;
  const nearCut = Math.min(Math.abs(hue - T.undertone.cool_max_hue), Math.abs(hue - T.undertone.warm_min_hue)) <= edge;

  let score = 0;
  const reasons: string[] = [];
  if (calibrated === good.length) {
    score += 2;
    reasons.push("Calibrated with white paper, so the camera’s color cast is removed.");
  } else if (calibrated) {
    score += 1;
    reasons.push("Some photos were calibrated with white paper.");
  } else reasons.push("Not calibrated: lighting may shift the read. A white-paper photo helps most.");
  if (good.length >= 2 && agree) {
    score += 1;
    reasons.push(`${good.length} photos agree on your undertone.`);
  } else if (good.length >= 2) {
    score -= 1;
    reasons.push(`Your photos disagree (${[...new Set(tones)].join(" vs ")}), so this is a middle read.`);
  } else reasons.push("Only one photo so far. A second one in different daylight makes it more reliable.");
  if (nearCut) {
    score -= 1;
    reasons.push("Your undertone sits close to a cutoff between two bands.");
  }
  const confidence: Confidence = score >= 3 ? "high" : score >= 1 ? "medium" : "low";
  const shapes = reads.map((r) => r.ratios);
  return {
    measurements: {
      skin_lab: lab.map((v) => Math.round(v * 100) / 100) as Lab,
      hair_L: hair.length ? Math.round(median(hair) * 100) / 100 : null,
      hue: Math.round(hue * 100) / 100,
      ita: Math.round(itaDeg(lab) * 100) / 100,
      photos_used: good.length,
      hue_spread:
        good.length > 1
          ? Math.round(
              (Math.max(...good.map((r) => hueDeg(r.lab))) - Math.min(...good.map((r) => hueDeg(r.lab)))) * 10,
            ) / 10
          : 0,
      calibrated_photos: calibrated,
      lighting_note: good[0]?.lighting ?? null,
      face_ratios: reads.length ? reads.reduce((a, b) => (a.ratios.yaw <= b.ratios.yaw ? a : b)).ratios : null,
      face_shape: voteShape(shapes),
      face_shape_votes: shapes.map(classifyFace),
      body_ratios: body,
      source: "colors-page",
    },
    confidence,
    reasons,
    askSecond: good.length < 2 || !agree,
  };
}

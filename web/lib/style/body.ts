// Body proportions from Pose landmarks: neutral fit notes. A port of worker/closet_worker/vision/body.py.
import { T } from "./data";

export type PoseLm = [number, number, number]; // x px, y px, visibility
export type BodyRatios = { shoulder_hip: number; leg_torso: number };
const NEEDED = [11, 12, 23, 24, 27, 28];
const mid = (a: PoseLm, b: PoseLm): [number, number] => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
const d = (a: [number, number], b: [number, number]) => Math.hypot(a[0] - b[0], a[1] - b[1]);

export function bodyRatios(lm: PoseLm[]): BodyRatios | null {
  const vis = T.body.min_visibility!;
  if (lm.length < 29 || NEEDED.some((i) => lm[i]![2] < vis)) return null;
  const shoulder = d([lm[11]![0], lm[11]![1]], [lm[12]![0], lm[12]![1]]);
  const hip = d([lm[23]![0], lm[23]![1]], [lm[24]![0], lm[24]![1]]);
  const torso = d(mid(lm[11]!, lm[12]!), mid(lm[23]!, lm[24]!));
  const leg = d(mid(lm[23]!, lm[24]!), mid(lm[27]!, lm[28]!));
  if (Math.min(hip, torso) <= 0) return null;
  return { shoulder_hip: shoulder / hip, leg_torso: leg / torso };
}

export function fitNotes(r: BodyRatios | null): { area: string; advice: string }[] {
  const b = T.body;
  const notes = [
    { area: "Shirts", advice: "Shoulder seam right on the shoulder point; sleeves ending at the wrist bone." },
  ];
  if (!r) {
    notes.push({ area: "Photo", advice: "Add a front photo that shows you head to ankles for more fit notes." });
    return notes;
  }
  if (r.shoulder_hip >= b.broad_shoulders!)
    notes.push({
      area: "Jackets",
      advice: "Soft or natural shoulders sit well; straight or slightly tapered trousers keep the line balanced.",
    });
  else if (r.shoulder_hip <= b.narrow_shoulders!)
    notes.push({
      area: "Jackets",
      advice: "A little structure at the shoulder gives a clean line; straight-leg trousers pair well.",
    });
  else notes.push({ area: "Jackets", advice: "Most cuts work. Choose by how the shoulder seam and the waist sit." });
  if (r.leg_torso >= b.long_legs!)
    notes.push({
      area: "Trousers",
      advice: "A slight break at the shoe looks natural; tucked or untucked shirts both work.",
    });
  else if (r.leg_torso <= b.short_legs!)
    notes.push({
      area: "Trousers",
      advice: "A minimal break and a mid rise keep a clean line; shirts work well tucked or cropped at the hip.",
    });
  else notes.push({ area: "Trousers", advice: "A slight taper with a minimal break is an easy default." });
  notes.push({
    area: "Shoes",
    advice: "Match the shoe to the trouser: sleek profiles with tapered legs, chunkier soles with wider ones.",
  });
  return notes;
}

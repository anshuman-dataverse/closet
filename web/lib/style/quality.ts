// Photo checks: each failure says what to retake (guided capture).
import { median, srgbToLab } from "./color";
import { T } from "./data";
import { type BodyRatios, bodyRatios, type PoseLm } from "./body";
import { faceRatios } from "./face-shape";
import { faceWidth, readSkin } from "./skin";
import type { Box } from "./calibrate";
import type { Pixels, Point } from "./types";

export type Check = { ok: boolean; problems: string[] };

export function faceBox(pts: Point[]): Box {
  const xs = pts.map((p) => p[0]),
    ys = pts.map((p) => p[1]);
  return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
}

export function checkFace(img: Pixels, faces: Point[][]): Check {
  if (faces.length === 0)
    return { ok: false, problems: ["No face found. Use a clear photo of your face, looking at the camera."] };
  if (faces.length > 1) return { ok: false, problems: ["More than one face found. Use a photo with just you."] };
  const pts = faces[0]!;
  const problems: string[] = [];
  if (faceRatios(pts).yaw > (T.face_shape.max_yaw ?? 0.12)) problems.push("Face the camera straight on, then retake.");
  if (faceWidth(pts) / img.width < 0.18) problems.push("Move closer: your face should fill more of the photo.");
  const px = readSkin(img, pts).facePixels;
  const L = median(px.map(([r, g, b]) => srgbToLab(r!, g!, b!)[0]));
  if (L < T.lighting.dark_face_L) problems.push("The photo is too dark. Retake near a window in daylight.");
  if (px.filter((p) => Math.max(...p) >= 250).length / Math.max(1, px.length) > T.lighting.blown_share)
    problems.push("Part of your face is overexposed. Step out of direct sun and retake.");
  return { ok: problems.length === 0, problems };
}

export function checkBody(people: PoseLm[][]): Check & { ratios: BodyRatios | null } {
  if (people.length === 0)
    return { ok: false, problems: ["No person found. Use a full-length photo of you standing."], ratios: null };
  if (people.length > 1)
    return { ok: false, problems: ["More than one person found. Use a photo of just you."], ratios: null };
  const ratios = bodyRatios(people[0]!);
  if (!ratios)
    return { ok: false, problems: ["Make sure your shoulders, hips and ankles are all in the photo."], ratios: null };
  return { ok: true, problems: [], ratios };
}

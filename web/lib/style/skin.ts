// Skin, hair and lighting reads from Face Mesh points. A port of worker/closet_worker/vision/skin.py.
import { type Lab, median, srgbToLab } from "./color";
import { T } from "./data";
import type { Pixels, Point } from "./types";

export const CHEEK_L = 50,
  CHEEK_R = 280,
  FOREHEAD = 151,
  TOP = 10,
  CHIN = 152,
  LEFT = 234,
  RIGHT = 454,
  NOSE = 1;

// Every spot skin is read from (cheeks, under the eyes, cheekbones, lower cheeks, mid-forehead). Spots that
// don't look like the rest (a cap's shadow, glasses, paper, a beard) are dropped. Same list as skin.py.
export const SPOTS: Record<string, number> = {
  cheek_l: 50,
  cheek_r: 280,
  under_eye_l: 101,
  under_eye_r: 330,
  cheekbone_l: 117,
  cheekbone_r: 346,
  low_cheek_l: 205,
  low_cheek_r: 425,
  forehead: 151,
};

const dist = (a: Point, b: Point) => Math.hypot(a[0] - b[0], a[1] - b[1]);
export const faceWidth = (pts: Point[]) => dist(pts[LEFT]!, pts[RIGHT]!);

function disk(img: Pixels, c: Point, r: number, out: number[][]) {
  const x0 = Math.max(0, Math.ceil(c[0] - r)),
    x1 = Math.min(img.width - 1, Math.floor(c[0] + r));
  const y0 = Math.max(0, Math.ceil(c[1] - r)),
    y1 = Math.min(img.height - 1, Math.floor(c[1] + r));
  for (let y = y0; y <= y1; y++)
    for (let x = x0; x <= x1; x++)
      if ((x - c[0]) ** 2 + (y - c[1]) ** 2 <= r * r) {
        const i = (y * img.width + x) * 4;
        out.push([img.data[i]!, img.data[i + 1]!, img.data[i + 2]!]);
      }
}

export type SkinRead = { lab: Lab; hairL: number | null; facePixels: number[][]; dropped: string[] };

/** Skin pixels from the spots that agree with each other, and the names of those dropped. */
export function sampleSpots(img: Pixels, pts: Point[]): { px: number[][]; dropped: string[] } {
  const st = T.skin_sample;
  const r = Math.max(3, 0.04 * faceWidth(pts));
  const meds = new Map<string, Lab>();
  const pix = new Map<string, number[][]>();
  for (const [name, i] of Object.entries(SPOTS)) {
    const px: number[][] = [];
    disk(img, pts[i]!, r, px);
    if (!px.length) continue;
    const ok: number[][] = [];
    const okLab: Lab[] = [];
    for (const p of px) {
      const l = srgbToLab(p[0]!, p[1]!, p[2]!);
      const paper = l[0] > st.paper_L && Math.hypot(l[1], l[2]) < st.paper_chroma;
      if (!paper && l[0] >= st.dark_L) {
        ok.push(p);
        okLab.push(l);
      }
    }
    if (ok.length / px.length < st.min_skin_share) continue;
    meds.set(name, [0, 1, 2].map((k) => median(okLab.map((l) => l[k]!))) as Lab);
    pix.set(name, ok);
  }
  if (!meds.size) {
    const px: number[][] = [];
    for (const i of [CHEEK_L, CHEEK_R, FOREHEAD]) disk(img, pts[i]!, r, px);
    return { px, dropped: Object.keys(SPOTS) };
  }
  const all = [...meds.values()];
  const centre = [0, 1, 2].map((k) => median(all.map((m) => m[k]!)));
  let keep = [...meds.entries()]
    .filter(([, m]) => Math.hypot(m[0] - centre[0]!, m[1] - centre[1]!, m[2] - centre[2]!) <= st.max_delta_e)
    .map(([n]) => n);
  if (keep.length < 2) keep = [...meds.keys()];
  return {
    px: keep.flatMap((n) => pix.get(n)!),
    dropped: Object.keys(SPOTS).filter((n) => !keep.includes(n)),
  };
}

export function readSkin(img: Pixels, pts: Point[]): SkinRead {
  const { px, dropped } = sampleSpots(img, pts);
  const labs = px.map(([R, G, B]) => srgbToLab(R!, G!, B!));
  const lab: Lab = [median(labs.map((l) => l[0])), median(labs.map((l) => l[1])), median(labs.map((l) => l[2]))];
  const top = pts[TOP]!,
    fh = dist(pts[TOP]!, pts[CHIN]!);
  const L = pts[LEFT]!,
    R = pts[RIGHT]!;
  const [xa, xb] = [L[0] + 0.25 * (R[0] - L[0]), R[0] - 0.25 * (R[0] - L[0])].sort((a, b) => a - b) as [number, number];
  const y0 = Math.trunc(Math.max(0, top[1] - 0.22 * fh)),
    y1 = Math.trunc(Math.max(0, top[1] - 0.08 * fh));
  const bx0 = Math.trunc(Math.max(0, xa)),
    bx1 = Math.trunc(Math.max(0, xb));
  const hair: number[] = [];
  for (let y = y0; y < Math.min(y1, img.height); y++)
    for (let x = bx0; x < Math.min(bx1, img.width); x++) {
      const i = (y * img.width + x) * 4;
      hair.push(srgbToLab(img.data[i]!, img.data[i + 1]!, img.data[i + 2]!)[0]);
    }
  return { lab, hairL: hair.length >= 20 ? median(hair) : null, facePixels: px, dropped };
}

export function undertone(lab: Lab): string {
  const u = T.undertone;
  const [, a, b] = lab;
  if (a <= u.olive_max_a && b >= u.olive_b[0] && b <= u.olive_b[1]) return "olive";
  const h = (Math.atan2(b, a) * 180) / Math.PI;
  if (h >= u.warm_min_hue) return "warm";
  if (h <= u.cool_max_hue) return "cool";
  return "neutral";
}

export function depth(lab: Lab): string {
  const ita = (Math.atan2(lab[0] - 50, Math.max(lab[2], 1e-6)) * 180) / Math.PI;
  return ita > T.depth.light_min_ita ? "light" : ita < T.depth.deep_max_ita ? "deep" : "medium";
}

export function contrast(skinL: number, hairL: number | null): string | null {
  if (hairL === null) return null;
  const d = Math.abs(skinL - hairL);
  return d < T.contrast.low_below ? "low" : d > T.contrast.high_above ? "high" : "medium";
}

/** A retake hint when the face is dark, the light has a strong color cast, or highlights are blown. */
export function lightingNote(img: Pixels, facePixels: number[][], calibrated: boolean): string | null {
  const li = T.lighting;
  const faceL = median(facePixels.map(([r, g, b]) => srgbToLab(r!, g!, b!)[0]));
  const sy = Math.max(1, Math.floor(img.height / 200)),
    sx = Math.max(1, Math.floor(img.width / 200));
  let n = 0,
    A = 0,
    B = 0;
  for (let y = 0; y < img.height; y += sy)
    for (let x = 0; x < img.width; x += sx) {
      const i = (y * img.width + x) * 4;
      const l = srgbToLab(img.data[i]!, img.data[i + 1]!, img.data[i + 2]!);
      A += l[1];
      B += l[2];
      n++;
    }
  const wa = A / n,
    wb = B / n;
  const dark = faceL < li.dark_face_L;
  const warm = !calibrated && (wb > li.warm_cast_b || wa > li.cast_a);
  const cool = !calibrated && wb < li.cool_cast_b;
  const blown =
    facePixels.filter((p) => Math.max(...p) >= 250).length / Math.max(1, facePixels.length) > li.blown_share;
  if (dark && warm) return "Lighting looks warm and dim. Retake near a window for a better read.";
  if (dark) return "The photo is quite dark. Retake near a window in daylight for a better read.";
  if (warm) return "Lighting looks warm, which can shift the read. Retake in daylight, away from lamps.";
  if (cool) return "Lighting looks cool or blue. Retake in daylight for a better read.";
  if (blown) return "Some of your face is overexposed. Retake out of direct sun for a better read.";
  return null;
}

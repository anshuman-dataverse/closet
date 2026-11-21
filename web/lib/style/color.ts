// CIE colorimetry (sRGB D65 → XYZ → L*a*b*), matching scikit-image's rgb2lab used by the Mac worker.

export type Lab = [number, number, number];

const M = [
  [0.412453, 0.35758, 0.180423],
  [0.212671, 0.71516, 0.072169],
  [0.019334, 0.119193, 0.950227],
] as const;
const WHITE = [0.95047, 1.0, 1.08883] as const; // D65, 2° observer

export const toLinear = (c8: number): number => {
  const c = c8 / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
};

export const fromLinear = (l: number): number => {
  const c = l <= 0.0031308 ? 12.92 * l : 1.055 * l ** (1 / 2.4) - 0.055;
  return Math.max(0, Math.min(255, Math.round(c * 255)));
};

const f = (t: number) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);

export function linearToLab(r: number, g: number, b: number): Lab {
  const x = (M[0][0] * r + M[0][1] * g + M[0][2] * b) / WHITE[0];
  const y = (M[1][0] * r + M[1][1] * g + M[1][2] * b) / WHITE[1];
  const z = (M[2][0] * r + M[2][1] * g + M[2][2] * b) / WHITE[2];
  const fx = f(x),
    fy = f(y),
    fz = f(z);
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}

export const srgbToLab = (r: number, g: number, b: number): Lab => linearToLab(toLinear(r), toLinear(g), toLinear(b));

export const hueDeg = (lab: Lab): number => (Math.atan2(lab[2], lab[1]) * 180) / Math.PI;
export const itaDeg = (lab: Lab): number => (Math.atan2(lab[0] - 50, Math.max(lab[2], 1e-6)) * 180) / Math.PI;
export const chroma = (lab: Lab): number => Math.hypot(lab[1], lab[2]);

export function median(xs: number[]): number {
  if (!xs.length) return NaN;
  const s = [...xs].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m]! : (s[m - 1]! + s[m]!) / 2;
}

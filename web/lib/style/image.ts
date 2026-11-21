"use client";
import type { Pixels } from "./types";

export const DECODE_ERROR = "That photo couldn’t be opened. Try a JPEG or PNG.";

/** Decodes a photo on this device (orientation applied), capped at 1600px. Nothing leaves the browser. */
export async function decodePhoto(
  file: Blob,
  max = 1600,
): Promise<{ canvas: HTMLCanvasElement; pixels: Pixels; url: string }> {
  let bmp: ImageBitmap;
  try {
    bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    throw new Error(DECODE_ERROR);
  }
  const s = Math.min(1, max / Math.max(bmp.width, bmp.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(bmp.width * s));
  canvas.height = Math.max(1, Math.round(bmp.height * s));
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error(DECODE_ERROR);
  ctx.drawImage(bmp, 0, 0, canvas.width, canvas.height);
  bmp.close();
  const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
  return { canvas, pixels: { data: img.data, width: img.width, height: img.height }, url: URL.createObjectURL(file) };
}

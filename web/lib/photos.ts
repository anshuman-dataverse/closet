"use client";
// Photo capture pipeline (SPEC 6): decode with orientation, resize to a 1600px JPEG (q≈0.85) and a
// 480px thumbnail. Re-encoding through a canvas drops EXIF, including GPS location.

import type { Db } from "@/lib/supabase/types";

export const FULL_EDGE = 1600;
export const THUMB_EDGE = 480;
export const DECODE_ERROR = "That photo couldn’t be opened. Try a JPEG or PNG.";

/** Scale (w, h) so the long edge is at most max. Never upscales. */
export function fitWithin(w: number, h: number, max: number): { w: number; h: number } {
  const s = Math.min(1, max / Math.max(w, h));
  return { w: Math.max(1, Math.round(w * s)), h: Math.max(1, Math.round(h * s)) };
}

type Source = { el: CanvasImageSource; w: number; h: number; close?: () => void };

async function decode(file: Blob): Promise<Source> {
  if (typeof createImageBitmap === "function") {
    try {
      const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
      return { el: bmp, w: bmp.width, h: bmp.height, close: () => bmp.close() };
    } catch {
      /* fall through to <img> */
    }
  }
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((res, rej) => {
      const i = new Image();
      i.onload = () => res(i);
      i.onerror = () => rej(new Error("decode"));
      i.src = url;
    });
    return { el: img, w: img.naturalWidth, h: img.naturalHeight };
  } finally {
    URL.revokeObjectURL(url);
  }
}

function encode(src: Source, max: number, quality: number): Promise<Blob> {
  const { w, h } = fitWithin(src.w, src.h, max);
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d");
  if (!ctx) return Promise.reject(new Error("canvas"));
  ctx.fillStyle = "#fff"; // transparent PNGs become white, not black
  ctx.fillRect(0, 0, w, h);
  ctx.drawImage(src.el, 0, 0, w, h);
  return new Promise((res, rej) => c.toBlob((b) => (b ? res(b) : rej(new Error("encode"))), "image/jpeg", quality));
}

export type PreparedPhoto = { full: Blob; thumb: Blob; previewUrl: string };

export async function preparePhoto(file: Blob): Promise<PreparedPhoto> {
  let src: Source;
  try {
    src = await decode(file);
  } catch {
    throw new Error(DECODE_ERROR);
  }
  if (!src.w || !src.h) throw new Error(DECODE_ERROR);
  try {
    const full = await encode(src, FULL_EDGE, 0.85);
    const thumb = await encode(src, THUMB_EDGE, 0.8);
    return { full, thumb, previewUrl: URL.createObjectURL(thumb) };
  } catch {
    throw new Error(DECODE_ERROR);
  } finally {
    src.close?.();
  }
}

export const BUCKET = "wardrobe";

/** Uploads to {uid}/items/{itemId}/{uuid}.jpg and _thumb.jpg. */
export async function uploadItemPhoto(
  db: Db,
  uid: string,
  itemId: string,
  p: PreparedPhoto,
): Promise<{ photo_path: string; thumb_path: string }> {
  const base = `${uid}/items/${itemId}/${crypto.randomUUID()}`;
  const photo_path = `${base}.jpg`;
  const thumb_path = `${base}_thumb.jpg`;
  const opts = { contentType: "image/jpeg", upsert: false, cacheControl: "31536000" };
  const [a, b] = await Promise.all([
    db.storage.from(BUCKET).upload(photo_path, p.full, opts),
    db.storage.from(BUCKET).upload(thumb_path, p.thumb, opts),
  ]);
  if (a.error || b.error) {
    await removePaths(db, [photo_path, thumb_path]);
    throw new Error("The photo didn’t upload. Check your connection and try again.");
  }
  return { photo_path, thumb_path };
}

export async function removePaths(db: Db, paths: readonly (string | null | undefined)[]): Promise<void> {
  const list = paths.filter((p): p is string => !!p);
  if (list.length) await db.storage.from(BUCKET).remove(list);
}

/** Every file under {uid}/ (Storage lists one folder level at a time). */
export async function listAllFiles(db: Db, prefix: string): Promise<string[]> {
  const out: string[] = [];
  const walk = async (dir: string): Promise<void> => {
    for (let offset = 0; ; offset += 100) {
      const { data, error } = await db.storage.from(BUCKET).list(dir, { limit: 100, offset });
      if (error || !data?.length) return;
      for (const e of data) {
        const path = `${dir}/${e.name}`;
        if (e.id === null) await walk(path);
        else out.push(path);
      }
      if (data.length < 100) return;
    }
  };
  await walk(prefix);
  return out;
}

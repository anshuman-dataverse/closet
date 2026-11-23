"use client";
/* eslint-disable @next/next/no-img-element -- signed, private Storage URLs; next/image can't optimize them */

import type { CSSProperties } from "react";
import type { Item } from "@/lib/closet/types";
import { isDark, swatchFor } from "@/lib/domain/colors";
import { useSignedUrl } from "@/lib/signed-urls";

export const studioThumb = (p: string | null | undefined) => (p ? p.replace(/\.jpg$/, "_thumb.jpg") : null);

const Hanger = () => (
  <svg className="ph-ico" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M10 6.2a2 2 0 1 1 3 1.7c-.6.4-1 .9-1 1.6v.7" />
    <path d="M12 10.2 3.6 16a1 1 0 0 0 .6 1.8h15.6a1 1 0 0 0 .6-1.8z" />
  </svg>
);

/**
 * A piece's picture: the studio image (once the Mac makes one), else the cut-out, else the photo,
 * else its color swatch. Tiles use the studio thumbnail; large views use the full studio image.
 * `bare` is for tiles where the name is printed below: empty alt and a hanger icon instead of the name.
 */
export function PieceCell({
  item,
  bare = false,
  large = false,
  prefer = "studio",
}: {
  item: Item;
  bare?: boolean;
  large?: boolean;
  prefer?: "studio" | "photo";
}) {
  const studio =
    prefer === "studio" && item.studio_path ? (large ? item.studio_path : studioThumb(item.studio_path)) : null;
  const cut = prefer === "studio" ? item.cutout_path : null;
  const path = studio ?? cut ?? (large ? item.photo_path : item.thumb_path) ?? item.photo_path;
  const url = useSignedUrl(path);
  const sw = swatchFor(item);
  const style = (sw ? { "--sw": sw } : undefined) as CSSProperties | undefined;
  if (path && url) {
    return (
      <img
        src={url}
        alt={bare ? "" : item.name}
        className={cut ? "cut" : undefined}
        loading="lazy"
        decoding="async"
        style={style}
      />
    );
  }
  return (
    <span className={`ph${sw ? (isDark(sw) ? " dk" : " lt") : ""}`} style={style}>
      {bare ? <Hanger /> : item.name}
    </span>
  );
}

/** 1–4 pieces on the paper panel. With 3, one tall photo on the left and two squares on the right. */
export function Flatlay({ pieces, className = "" }: { pieces: readonly Item[]; className?: string }) {
  const shown = pieces.slice(0, 4);
  const n = Math.max(1, shown.length);
  return (
    <div className={`flatlay n${n} ${className}`.trim()}>
      {shown.length ? (
        shown.map((p, k) => <PieceCell key={p.id} item={p} large={n === 1 || (n === 3 && k === 0)} />)
      ) : (
        <span className="ph">No pieces</span>
      )}
      {pieces.length > 4 && <span className="more">+{pieces.length - 4}</span>}
    </div>
  );
}

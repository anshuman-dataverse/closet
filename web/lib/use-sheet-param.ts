"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

/** Sheets are addressed by query params (e.g. /closet?item=…), so they deep-link and close on Back. */
export function useSheetParam() {
  const params = useSearchParams();
  const router = useRouter();
  const path = usePathname();
  const open = useCallback(
    (key: string, value: string) => {
      const q = new URLSearchParams(params.toString());
      for (const k of ["item", "add", "outfit", "edit", "new"]) q.delete(k);
      q.set(key, value);
      router.push(`${path}?${q}`, { scroll: false });
    },
    [params, path, router],
  );
  const close = useCallback(() => {
    const q = new URLSearchParams(params.toString());
    for (const k of ["item", "add", "outfit", "edit", "new"]) q.delete(k);
    const s = q.toString();
    router.replace(s ? `${path}?${s}` : path, { scroll: false });
  }, [params, path, router]);
  return { params, open, close };
}

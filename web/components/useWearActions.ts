"use client";

import { useCallback } from "react";
import { useToast } from "@/components/Toast";
import { logWear, removeWear } from "@/lib/closet/store";
import type { Outfit } from "@/lib/closet/types";
import type { Occasion } from "@/lib/occasions";

/** "Wear this" → "Logged for today" with Undo; the same outfit twice in a day → "Already logged". */
export function useWearActions() {
  const toast = useToast();

  const wear = useCallback(
    async (o: Pick<Outfit, "id" | "itemIds">, occasion: Occasion, day: string, isToday = true) => {
      try {
        const r = await logWear({ wornOn: day, occasion, outfitId: o.id, itemIds: o.itemIds });
        const when = isToday && day ? "today" : "that day";
        if (r.status === "already") {
          toast(`Already logged for ${when}`);
          return r;
        }
        toast(`Logged for ${when}`, {
          action: "Undo",
          onAction: () => void removeWear(r.id).catch(() => toast("Couldn’t undo. Remove it from Recently worn.")),
        });
        return r;
      } catch (e) {
        toast((e as Error).message);
        return null;
      }
    },
    [toast],
  );

  const unwear = useCallback(
    async (id: string) => {
      try {
        await removeWear(id);
        toast("Removed from your log");
      } catch (e) {
        toast((e as Error).message);
      }
    },
    [toast],
  );

  return { wear, unwear };
}

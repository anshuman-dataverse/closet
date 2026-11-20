import type { Metadata } from "next";
import { Suspense } from "react";
import { OutfitsView } from "./OutfitsView";

export const metadata: Metadata = { title: "Outfits" };

export default function OutfitsPage() {
  return (
    <Suspense fallback={null}>
      <OutfitsView />
    </Suspense>
  );
}

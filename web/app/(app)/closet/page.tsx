import type { Metadata } from "next";
import { Suspense } from "react";
import { ClosetView } from "./ClosetView";

export const metadata: Metadata = { title: "Closet" };

export default function ClosetPage() {
  return (
    <Suspense fallback={null}>
      <ClosetView />
    </Suspense>
  );
}

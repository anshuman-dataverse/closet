import type { Metadata } from "next";
import { Suspense } from "react";
import { TodayView } from "./TodayView";

export const metadata: Metadata = { title: "Today" };

export default function TodayPage() {
  return (
    <Suspense fallback={null}>
      <TodayView />
    </Suspense>
  );
}

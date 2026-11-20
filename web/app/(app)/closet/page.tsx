import type { Metadata } from "next";
import { EmptyState } from "@/components/EmptyState";

export const metadata: Metadata = { title: "Closet" };

export default function ClosetPage() {
  return (
    <>
      <div className="page-head">
        <h1>Closet</h1>
        <p className="muted">0 pieces</p>
      </div>
      <EmptyState title="Nothing here yet">
        Snap a photo of each piece you own. Your Mac can fill in the name, color and where it fits, so each one takes a
        few seconds.
      </EmptyState>
    </>
  );
}

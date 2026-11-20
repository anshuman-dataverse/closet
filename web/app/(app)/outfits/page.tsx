import type { Metadata } from "next";
import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";

export const metadata: Metadata = { title: "Outfits" };

export default function OutfitsPage() {
  return (
    <>
      <div className="page-head">
        <h1>Outfits</h1>
        <p className="muted">0 outfits</p>
      </div>
      <EmptyState
        title="No outfits yet"
        actions={
          <Link className="btn primary" href="/closet">
            Add clothes
          </Link>
        }
      >
        Add a few clothes first, then put them together here.
      </EmptyState>
    </>
  );
}

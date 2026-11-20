import type { Metadata } from "next";
import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";

export const metadata: Metadata = { title: "Spend" };

export default function SpendPage() {
  return (
    <>
      <div className="page-head">
        <h1>Spend</h1>
      </div>
      <EmptyState
        title="No prices yet"
        actions={
          <Link className="btn primary" href="/closet">
            Add clothes
          </Link>
        }
      >
        Add what you paid when you add clothes. This page then shows what you spend each month and which pieces earn
        their keep.
      </EmptyState>
    </>
  );
}

import type { Metadata } from "next";
import { Suspense } from "react";
import { ShopTabs } from "./ShopTabs";

export const metadata: Metadata = { title: "Shop" };

export default function ShopPage() {
  return (
    <>
      <div className="page-head">
        <h1>Shop</h1>
      </div>
      <Suspense fallback={null}>
        <ShopTabs />
      </Suspense>
    </>
  );
}

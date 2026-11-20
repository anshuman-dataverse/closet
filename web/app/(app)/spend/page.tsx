import type { Metadata } from "next";
import { SpendView } from "./SpendView";

export const metadata: Metadata = { title: "Spend" };

export default function SpendPage() {
  return <SpendView />;
}

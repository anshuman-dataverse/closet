import type { Metadata } from "next";
import Link from "next/link";
import { ColorsCheck } from "./ColorsCheck";

export const metadata: Metadata = {
  title: "Find your colors",
  description: "A free color check that runs on your device. Your photos are never uploaded.",
};

export default function ColorsPage() {
  return (
    <>
      <header className="top">
        <div className="top-in">
          <Link className="mark" href="/colors" aria-label="Closet colors">
            closet
          </Link>
        </div>
      </header>
      <main id="view" className="wrap" tabIndex={-1} style={{ paddingBottom: 48 }}>
        <div className="page-head">
          <h1>Find your colors</h1>
        </div>
        <ColorsCheck />
      </main>
    </>
  );
}

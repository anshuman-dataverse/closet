import type { Metadata } from "next";
import { EmptyState } from "@/components/EmptyState";
import { signOut } from "@/app/login/actions";
import { WorkerPanel } from "./WorkerPanel";

export const metadata: Metadata = { title: "Style profile" };

export default function ProfilePage() {
  return (
    <>
      <div className="page-head">
        <h1>Style profile</h1>
      </div>

      <section className="block" aria-labelledby="photos-h">
        <div className="block-head">
          <h2 id="photos-h">Style photos</h2>
        </div>
        <EmptyState title="No photos yet">
          Up to 6: front, side and back in fitted clothes, plus a face close-up in daylight with no filter.
        </EmptyState>
        <p className="muted small privacy">
          Your photos are analyzed on your Mac. Model training may run in your own Google Colab.
        </p>
      </section>

      <WorkerPanel />

      <section className="block" aria-labelledby="account-h">
        <div className="block-head">
          <h2 id="account-h">Account</h2>
        </div>
        <form action={signOut}>
          <button type="submit" className="btn">
            Sign out
          </button>
        </form>
      </section>
    </>
  );
}

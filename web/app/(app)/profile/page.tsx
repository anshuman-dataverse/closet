import type { Metadata } from "next";
import { signOut } from "@/app/login/actions";
import { SettingsPanel } from "./SettingsPanel";
import { StyleSection } from "./StyleSection";
import { WorkerPanel } from "./WorkerPanel";

export const metadata: Metadata = { title: "Style profile" };

export default function ProfilePage() {
  return (
    <>
      <div className="page-head">
        <h1>Style profile</h1>
      </div>

      <StyleSection />

      <SettingsPanel />

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

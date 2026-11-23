import type { Metadata } from "next";
import { signOut } from "@/app/login/actions";
import { DeleteAll, SettingsPanel } from "./SettingsPanel";
import { StyleSection } from "./StyleSection";
import { WorkerPanel } from "./WorkerPanel";

export const metadata: Metadata = { title: "Style profile" };

export default function ProfilePage() {
  return (
    <>
      <div className="page-head">
        <h1>Style profile</h1>
      </div>
      <nav className="jump" aria-label="On this page">
        <a href="#style">Style</a>
        <a href="#sizes">Sizes and fit</a>
        <a href="#shopping">Shopping</a>
        <a href="#place">Place</a>
        <a href="#mac">Your Mac</a>
        <a href="#account">Account</a>
      </nav>

      <div id="style" />
      <StyleSection />

      <SettingsPanel />

      <WorkerPanel />

      <section className="block" id="account" aria-labelledby="account-h">
        <div className="block-head">
          <h2 id="account-h">Account</h2>
        </div>
        <form action={signOut}>
          <button type="submit" className="btn">
            Sign out
          </button>
        </form>
        <DeleteAll />
      </section>
    </>
  );
}

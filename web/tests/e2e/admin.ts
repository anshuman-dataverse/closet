import { createClient } from "@supabase/supabase-js";
import type { Database } from "../../lib/database.types";
import { OWNER, SERVICE_KEY, SUPABASE_URL, WORKER_ID } from "./env";

export const admin = createClient<Database>(SUPABASE_URL, SERVICE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

export async function ensureUser(u: { id: string; email: string }) {
  await admin.auth.admin.deleteUser(u.id).catch(() => {});
  const { error } = await admin.auth.admin.createUser({ id: u.id, email: u.email, email_confirm: true });
  if (error) throw new Error(`createUser ${u.email}: ${error.message}`);
}

/** A one-time sign-in URL for our callback route (the same link format the email uses). */
export async function signInPath(email: string, next = "/today") {
  const { data, error } = await admin.auth.admin.generateLink({ type: "magiclink", email });
  if (error || !data.properties) throw new Error(`generateLink: ${error?.message}`);
  const q = new URLSearchParams({ token_hash: data.properties.hashed_token, type: "magiclink", next });
  return `/auth/callback?${q}`;
}

export async function resetWorkerState() {
  await admin.from("jobs").delete().eq("user_id", OWNER.id);
  await admin.from("workers").delete().eq("user_id", OWNER.id);
}

export async function backdateWorker(ms: number) {
  await admin
    .from("workers")
    .update({ last_seen_at: new Date(Date.now() - ms).toISOString() })
    .eq("id", WORKER_ID);
}

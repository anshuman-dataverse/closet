import { ensureUser } from "./admin";
import { OWNER, STRANGER, SUPABASE_URL } from "./env";

export default async function globalSetup() {
  const health = await fetch(`${SUPABASE_URL}/auth/v1/health`).catch(() => null);
  if (!health?.ok) throw new Error("Local Supabase isn't running. Start it with `supabase start` from the repo root.");
  await ensureUser(OWNER);
  await ensureUser(STRANGER);
}

// Creates ALLOWED_EMAIL (from .env.local) as a user in the LOCAL Supabase stack, so you can sign in
// during development. Sign-in emails land in Mailpit: http://127.0.0.1:55424
// Run: pnpm dev:user
import { createClient } from "@supabase/supabase-js";
import { readFileSync } from "node:fs";

const env = Object.fromEntries(
  readFileSync(new URL("../.env.local", import.meta.url), "utf8")
    .split("\n")
    .map((l) => l.replace(/#.*/, "").trim())
    .filter(Boolean)
    .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]),
);
const url = env.NEXT_PUBLIC_SUPABASE_URL;
if (!/^http:\/\/(127\.0\.0\.1|localhost)/.test(url)) throw new Error("dev-user only runs against the local stack");
// The public demo service key every local Supabase stack uses.
const LOCAL_SERVICE_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU";
const admin = createClient(url, LOCAL_SERVICE_KEY, { auth: { persistSession: false } });
const { data, error } = await admin.auth.admin.createUser({ email: env.ALLOWED_EMAIL, email_confirm: true });
if (error && !/already/i.test(error.message)) throw error;
console.log(error ? `${env.ALLOWED_EMAIL} already exists` : `created ${data.user.email} (${data.user.id})`);

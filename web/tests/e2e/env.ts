// Fixed values for the local Supabase stack. The service key below is the public demo key that
// every local stack ships with; it has no power outside 127.0.0.1.
export const SUPABASE_URL = process.env.E2E_SUPABASE_URL ?? "http://127.0.0.1:55421";
export const SERVICE_KEY =
  process.env.E2E_SERVICE_KEY ??
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU";
export const OWNER = { id: "0e2e0000-0000-4000-8000-000000000001", email: "owner@closet.test" };
export const STRANGER = { id: "0e2e0000-0000-4000-8000-000000000002", email: "stranger@closet.test" };
export const WORKER_ID = "mac-e2e";

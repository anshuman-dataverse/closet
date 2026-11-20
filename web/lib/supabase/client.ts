"use client";

import { createBrowserClient } from "@supabase/ssr";
import type { Database } from "@/lib/database.types";
import { SUPABASE_ANON_KEY, SUPABASE_URL } from "@/lib/env";
import type { Db } from "@/lib/supabase/types";

let client: Db | null = null;

/** One browser client per tab. RLS scopes every query to the signed-in user. */
export function supabase(): Db {
  client ??= createBrowserClient<Database>(SUPABASE_URL, SUPABASE_ANON_KEY);
  return client;
}

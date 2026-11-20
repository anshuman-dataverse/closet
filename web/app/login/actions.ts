"use server";

import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { isAllowedEmail, normalizeEmail, safeNext } from "@/lib/auth";
import { serverSupabase } from "@/lib/supabase/server";

export type LoginState = { step: "email" | "code"; email: string; error?: string; sent?: boolean };

/** Step 1: email the magic link + code. Other emails get the same reply, but nothing is sent. */
export async function sendLink(_: LoginState, form: FormData): Promise<LoginState> {
  const email = normalizeEmail(String(form.get("email") ?? ""));
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return { step: "email", email, error: "Enter your email address." };
  }
  if (!process.env.ALLOWED_EMAIL) {
    return { step: "email", email, error: "Sign-in isn’t set up yet. Set ALLOWED_EMAIL, then try again." };
  }
  if (isAllowedEmail(email, process.env.ALLOWED_EMAIL)) {
    const h = await headers();
    const origin = h.get("origin") ?? `https://${h.get("host")}`;
    const next = safeNext(String(form.get("next") ?? ""));
    const supabase = await serverSupabase();
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        shouldCreateUser: false,
        emailRedirectTo: `${origin}/auth/callback?next=${encodeURIComponent(next)}`,
      },
    });
    if (error && error.status === 429) {
      return { step: "email", email, error: "Too many tries. Wait a minute, then try again." };
    }
  }
  return { step: "code", email, sent: true, error: undefined };
}

/** Step 2: the 6-digit code. Works inside the installed iPhone app, where email links open Safari instead. */
export async function verifyCode(prev: LoginState, form: FormData): Promise<LoginState> {
  const email = normalizeEmail(prev.email);
  const token = String(form.get("code") ?? "").replace(/\D/g, "");
  if (token.length !== 6) return { ...prev, error: "Enter the 6-digit code from the email." };
  if (!isAllowedEmail(email, process.env.ALLOWED_EMAIL)) {
    return { ...prev, error: "That code didn’t work. Ask for a new one." };
  }
  const supabase = await serverSupabase();
  const { error } = await supabase.auth.verifyOtp({ email, token, type: "email" });
  if (error) return { ...prev, error: "That code didn’t work or has expired. Ask for a new one." };
  redirect(safeNext(String(form.get("next") ?? "")));
}

export async function signOut(): Promise<void> {
  const supabase = await serverSupabase();
  await supabase.auth.signOut();
  redirect("/login");
}

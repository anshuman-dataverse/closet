import type { EmailOtpType } from "@supabase/supabase-js";
import type { NextRequest } from "next/server";
import { isAllowedEmail, safeNext } from "@/lib/auth";
import { relativeRedirect } from "@/lib/redirect";
import { serverSupabase } from "@/lib/supabase/server";

// Magic-link landing. Handles both the PKCE `code` and the `token_hash` link formats,
// then checks ALLOWED_EMAIL on the server before letting the session stand.
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const next = safeNext(searchParams.get("next"));
  const code = searchParams.get("code");
  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const supabase = await serverSupabase();

  let ok = false;
  if (code) {
    ok = !(await supabase.auth.exchangeCodeForSession(code)).error;
  } else if (tokenHash && type) {
    ok = !(await supabase.auth.verifyOtp({ token_hash: tokenHash, type })).error;
  }
  if (!ok) return relativeRedirect("/login?error=link", 303);

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!isAllowedEmail(user?.email, process.env.ALLOWED_EMAIL)) {
    await supabase.auth.signOut();
    return relativeRedirect("/login?error=not-allowed", 303);
  }
  return relativeRedirect(next, 303);
}

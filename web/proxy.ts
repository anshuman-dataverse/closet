import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";
import { isAllowedEmail } from "@/lib/auth";
import { sameHostUrl } from "@/lib/redirect";

// Refreshes the Supabase session on every request, sends signed-out visitors to /login,
// and signs out anyone whose email isn't ALLOWED_EMAIL (the server-side check from SPEC 9).

const PUBLIC = ["/login", "/auth/"];

export async function proxy(request: NextRequest) {
  let response = NextResponse.next({ request });
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

  const supabase = createServerClient(url, key, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (list) => {
        for (const { name, value } of list) request.cookies.set(name, value);
        response = NextResponse.next({ request });
        for (const { name, value, options } of list) response.cookies.set(name, value, options);
      },
    },
  });

  const {
    data: { user },
  } = await supabase.auth.getUser();
  const path = request.nextUrl.pathname;
  const isPublic = PUBLIC.some((p) => path === p || path.startsWith(p));

  const redirectTo = (to: string, params: Record<string, string> = {}) => {
    const q = new URLSearchParams(params).toString();
    const r = NextResponse.redirect(sameHostUrl(request, q ? `${to}?${q}` : to));
    for (const c of response.cookies.getAll()) r.cookies.set(c);
    return r;
  };

  if (user && !isAllowedEmail(user.email, process.env.ALLOWED_EMAIL)) {
    await supabase.auth.signOut();
    return redirectTo("/login", { error: "not-allowed" });
  }
  if (!user && !isPublic) {
    return redirectTo("/login", path === "/" || path === "/today" ? {} : { next: path });
  }
  if (user && path === "/login") return redirectTo("/today");
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!_next/static|_next/image|favicon.ico|icon|apple-icon|manifest.webmanifest|icons/|robots.txt).*)",
      // Router prefetches only fetch static shells (no user data: everything loads in the browser under RLS).
      // Redirecting them to /login during sign-out produced 404s, so they skip the proxy.
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};

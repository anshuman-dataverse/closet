import { NextResponse } from "next/server";

/**
 * A redirect with a relative Location header. Next normalizes request.nextUrl's host
 * (for example 127.0.0.1 becomes localhost), and an absolute redirect to a different host
 * would drop the session cookie we just set. Browsers resolve relative Locations against
 * the URL they actually requested.
 */
export function relativeRedirect(pathAndQuery: string, status: 303 | 307 = 307): NextResponse {
  return new NextResponse(null, { status, headers: { Location: pathAndQuery } });
}

/** Absolute URL on the host the browser actually used (the Host header, not Next's normalized nextUrl). */
export function sameHostUrl(request: { headers: Headers; nextUrl: URL }, pathAndQuery: string): URL {
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host") ?? request.nextUrl.host;
  const proto = request.headers.get("x-forwarded-proto") ?? request.nextUrl.protocol.replace(":", "");
  return new URL(pathAndQuery, `${proto}://${host}`);
}

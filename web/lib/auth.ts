// Only ALLOWED_EMAIL can use the app. Fails closed when it isn't set.

export function normalizeEmail(email: string | null | undefined): string {
  return (email ?? "").trim().toLowerCase();
}

export function isAllowedEmail(email: string | null | undefined, allowed: string | null | undefined): boolean {
  const a = normalizeEmail(allowed);
  return a.length > 0 && normalizeEmail(email) === a;
}

/** Only same-site paths are allowed as a post-login destination. */
export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return "/today";
  return next;
}

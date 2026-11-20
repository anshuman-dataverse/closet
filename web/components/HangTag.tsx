// Chalk hang tag for last-worn facts ("Last worn 12 days ago", "Never worn").
export function HangTag({ children, small = false }: { children: React.ReactNode; small?: boolean }) {
  return <span className={small ? "hangtag sm" : "hangtag"}>{children}</span>;
}

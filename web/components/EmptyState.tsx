// Empty states invite an action (SPEC 7, Copy).
export function EmptyState({
  title,
  children,
  actions,
}: {
  title: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <section className="empty">
      <h2>{title}</h2>
      <p>{children}</p>
      {actions && <div className="row">{actions}</div>}
    </section>
  );
}

"use client";

import { useEffect, useId, useRef } from "react";

// Bottom sheet on phones, centered dialog at 700px+. Native <dialog> gives focus trap and Esc.
export function Sheet({
  open,
  onClose,
  title,
  children,
  actions,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="sheet"
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose(); // tap on the scrim
      }}
    >
      {open && (
        <div className="sheet-body">
          <button type="button" className="sheet-x" aria-label="Close" onClick={onClose}>
            ×
          </button>
          <h2 id={titleId}>{title}</h2>
          {children}
          {actions && <div className="sheet-actions">{actions}</div>}
        </div>
      )}
    </dialog>
  );
}

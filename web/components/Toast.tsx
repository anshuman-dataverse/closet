"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

type ToastOpts = { action?: string; onAction?: () => void; ms?: number };
type Show = (message: string, opts?: ToastOpts) => void;

const ToastContext = createContext<Show>(() => {});

export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [t, setT] = useState<{ id: number; message: string } & ToastOpts>();
  const [on, setOn] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const show = useCallback<Show>((message, opts = {}) => {
    clearTimeout(timer.current);
    setT({ id: Date.now(), message, ...opts });
    setOn(true);
    timer.current = setTimeout(() => setOn(false), opts.ms ?? (opts.action ? 6000 : 3500));
  }, []);

  useEffect(() => () => clearTimeout(timer.current), []);

  return (
    <ToastContext value={show}>
      {children}
      <div className={`toast${on ? " on" : ""}`} role="status" aria-live="polite">
        {t && (
          <>
            <span>{t.message}</span>
            {t.action && (
              <button
                type="button"
                className="toast-act"
                tabIndex={on ? 0 : -1}
                onClick={() => {
                  setOn(false);
                  t.onAction?.();
                }}
              >
                {t.action}
              </button>
            )}
          </>
        )}
      </div>
    </ToastContext>
  );
}

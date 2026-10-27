"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { errorMessage } from "@/lib/api/errors";

type Toast = { id: number; message: string };

const ToastContext = createContext<(message: string) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const notify = useCallback((message: string) => {
    const id = Date.now() + Math.random();
    setToasts((all) => [...all, { id, message }]);
    setTimeout(() => setToasts((all) => all.filter((t) => t.id !== id)), 5000);
  }, []);

  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 flex-col gap-2"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className="pointer-events-auto rounded-lg border border-input bg-popover px-4 py-2.5 text-sm shadow-lg"
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useNotify() {
  return useContext(ToastContext);
}

/** Run a write and show its error as a toast. `pending` is true while it runs. */
export function useAction() {
  const notify = useNotify();
  const [pending, setPending] = useState(false);
  const run = useCallback(
    async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
      setPending(true);
      try {
        return await fn();
      } catch (error) {
        notify(errorMessage(error));
        return undefined;
      } finally {
        setPending(false);
      }
    },
    [notify],
  );
  return useMemo(() => ({ run, pending }), [run, pending]);
}

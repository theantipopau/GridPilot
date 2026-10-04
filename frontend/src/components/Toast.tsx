import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { IconCheckCircle } from "./icons";

type ToastTone = "success" | "info";
interface ToastItem {
  id: number;
  message: string;
  tone: ToastTone;
}

const ToastContext = createContext<(message: string, tone?: ToastTone) => void>(() => {});

/** Brief confirmation that an action happened ("Approved 07ENG3"). Review
 *  queues refresh their list in place after a decision, so without this the
 *  only sign a click worked is a row quietly disappearing. Uses the same
 *  words as the button that was pressed, and never blocks anything. */
export function useToast() {
  return useContext(ToastContext);
}

const VISIBLE_MS = 3200;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const show = useCallback(
    (message: string, tone: ToastTone = "success") => {
      const id = nextId.current++;
      setToasts((t) => [...t.slice(-3), { id, message, tone }]);
    },
    [],
  );
  const value = useMemo(() => show, [show]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-5 right-5 z-[60] flex flex-col items-end gap-2 print:hidden"
      >
        {toasts.map((t) => (
          <ToastCard key={t.id} toast={t} onDone={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastCard({ toast, onDone }: { toast: ToastItem; onDone: () => void }) {
  useEffect(() => {
    const id = window.setTimeout(onDone, VISIBLE_MS);
    return () => window.clearTimeout(id);
  }, [onDone]);

  return (
    <div
      role="status"
      className="pointer-events-auto flex animate-panel-in items-center gap-2 rounded-lg border border-slate-200 bg-white py-2 pl-3 pr-2 text-sm text-slate-800 shadow-lg"
    >
      <IconCheckCircle className={`h-4 w-4 shrink-0 ${toast.tone === "success" ? "text-emerald-600" : "text-sky-600"}`} />
      <span>{toast.message}</span>
      <button
        type="button"
        onClick={onDone}
        aria-label="Dismiss"
        className="ml-1 rounded px-1.5 text-ink-muted hover:text-slate-700"
      >
        ✕
      </button>
    </div>
  );
}

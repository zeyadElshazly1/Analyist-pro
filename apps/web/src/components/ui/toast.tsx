"use client";

/**
 * Lightweight toast notification system.
 * Usage:
 *   import { toast } from "@/components/ui/toast";
 *   toast.success("Project created!");
 *   toast.error("Something went wrong");
 *   toast.info("Analyzing data…");
 */

import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
  duration: number;
}

// ── Global event bus ──────────────────────────────────────────────────────────
type Listener = (item: ToastItem) => void;
const listeners: Listener[] = [];

function emit(item: ToastItem) {
  listeners.forEach((fn) => fn(item));
}

let _idCounter = 0;
function nextId() {
  return `toast-${++_idCounter}-${Date.now()}`;
}

export const toast = {
  success: (message: string, duration = 3500) =>
    emit({ id: nextId(), type: "success", message, duration }),
  error: (message: string, duration = 5000) =>
    emit({ id: nextId(), type: "error", message, duration }),
  info: (message: string, duration = 3000) =>
    emit({ id: nextId(), type: "info", message, duration }),
};

// ── Individual toast ──────────────────────────────────────────────────────────
const ICON = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
};

const STYLE = {
  success: "border-emerald-500/30 bg-emerald-950/80 text-emerald-300",
  error:   "border-red-500/30 bg-red-950/80 text-red-300",
  info:    "border-indigo-500/30 bg-indigo-950/80 text-indigo-300",
};

function Toast({ item, onRemove }: { item: ToastItem; onRemove: (id: string) => void }) {
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const onRemoveRef = useRef(onRemove);

  useEffect(() => {
    onRemoveRef.current = onRemove;
  }, [onRemove]);

  function dismiss() {
    setVisible(false);
    setTimeout(() => onRemoveRef.current(item.id), 300);
  }

  useEffect(() => {
    // Animate in
    const raf = requestAnimationFrame(() => setVisible(true));
    // Auto-dismiss
    timerRef.current = setTimeout(() => dismiss(), item.duration);
    return () => {
      cancelAnimationFrame(raf);
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const Icon = ICON[item.type];

  return (
    <div
      role="alert"
      className={`flex items-start gap-3 rounded-xl border px-4 py-3 shadow-2xl shadow-black/40 backdrop-blur-xl text-sm transition-all duration-300 max-w-sm w-full ${STYLE[item.type]} ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"
      }`}
    >
      <Icon className="h-4 w-4 mt-0.5 flex-shrink-0" />
      <p className="flex-1 leading-snug">{item.message}</p>
      <button
        onClick={dismiss}
        className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
        aria-label="Dismiss notification"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

// ── Toast container ───────────────────────────────────────────────────────────
export function ToastContainer() {
  const [items, setItems] = useState<ToastItem[]>([]);

  useEffect(() => {
    function handler(item: ToastItem) {
      setItems((prev) => [...prev.slice(-4), item]); // Max 5 toasts
    }
    listeners.push(handler);
    return () => {
      const idx = listeners.indexOf(handler);
      if (idx >= 0) listeners.splice(idx, 1);
    };
  }, []);

  function remove(id: string) {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }

  if (items.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2 items-end pointer-events-none">
      {items.map((item) => (
        <div key={item.id} className="pointer-events-auto">
          <Toast item={item} onRemove={remove} />
        </div>
      ))}
    </div>
  );
}

// ── Auto-mount: inject into document.body if not already mounted ───────────────
let _mounted = false;

export function ensureToastMounted() {
  if (typeof window === "undefined" || _mounted) return;
  _mounted = true;
  const el = document.createElement("div");
  el.id = "toast-root";
  document.body.appendChild(el);
  const root = createRoot(el);
  root.render(<ToastContainer />);
}

"use client";

/**
 * ColumnSelect — a fully custom dropdown that replaces native <select> for
 * column/option pickers in dark-theme contexts.
 *
 * Why: Native <select> dropdowns delegate their popup rendering to the OS.
 * When the <select> carries `text-white`, that color is inherited by <option>
 * elements, making them invisible against the OS default white/light popup
 * background. There is no reliable CSS fix across all browsers/OS combos.
 *
 * This component owns the full popup DOM, enabling correct dark-mode styling,
 * search filtering for many columns, and consistent cross-browser behavior.
 */

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Search } from "lucide-react";

export interface ColumnSelectProps {
  value: string;
  options: string[];
  onChange: (val: string) => void;
  /** Optional human-readable labels keyed by option value */
  optionLabels?: Record<string, string>;
  placeholder?: string;
  label?: string;
  disabled?: boolean;
  /** Extra classes on the root wrapper div */
  className?: string;
}

export function ColumnSelect({
  value,
  options,
  onChange,
  optionLabels,
  placeholder = "Select…",
  label,
  disabled = false,
  className = "",
}: ColumnSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  // Show search box only when there are enough options to warrant it
  const showSearch = options.length > 8;

  const filtered = search.trim()
    ? options.filter((o) => {
        const label = optionLabels?.[o] ?? o;
        return label.toLowerCase().includes(search.toLowerCase().trim());
      })
    : options;

  // ── Close on outside click ────────────────────────────────────────────────
  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      if (!open) return;
      if (!containerRef.current?.contains(e.target as Node)) {
        setOpen(false);
        setSearch("");
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  // ── Close on Escape ───────────────────────────────────────────────────────
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && open) {
        setOpen(false);
        setSearch("");
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  // ── Auto-focus search field when dropdown opens ───────────────────────────
  useEffect(() => {
    if (open && showSearch) {
      const t = setTimeout(() => searchRef.current?.focus(), 40);
      return () => clearTimeout(t);
    }
  }, [open, showSearch]);

  function toggle() {
    if (disabled) return;
    setOpen((prev) => {
      if (prev) setSearch(""); // clear search on close
      return !prev;
    });
  }

  function select(opt: string) {
    onChange(opt);
    setOpen(false);
    setSearch("");
  }

  const isLoading = options.length === 0;
  const triggerLabel = value ? (optionLabels?.[value] ?? value) : null;

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {label && (
        <label className="mb-1 block text-xs text-white/50">{label}</label>
      )}

      {/* ── Trigger button ─────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={toggle}
        disabled={disabled || isLoading}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={[
          "flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm text-left transition-all duration-150",
          disabled || isLoading
            ? "cursor-not-allowed opacity-40 border-white/[0.06] bg-white/[0.02]"
            : "cursor-pointer border-white/[0.08] bg-white/[0.04] hover:border-white/[0.18] hover:bg-white/[0.07]",
          open && !disabled
            ? "border-indigo-500/60 bg-white/[0.06] ring-1 ring-inset ring-indigo-500/25"
            : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <span
          className={`flex-1 truncate leading-none ${
            triggerLabel ? "text-white" : "text-white/30"
          }`}
        >
          {isLoading ? "Loading…" : triggerLabel ?? placeholder}
        </span>
        <ChevronDown
          className={`h-3.5 w-3.5 flex-shrink-0 text-white/35 transition-transform duration-150 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {/* ── Dropdown panel ─────────────────────────────────────────────── */}
      {open && (
        <div
          role="listbox"
          className={[
            "absolute left-0 top-full z-50 mt-1.5 overflow-hidden rounded-xl",
            "border border-white/[0.12] bg-[#0d0d1c] shadow-2xl shadow-black/70 backdrop-blur-xl",
            // min-w = trigger width; max-w caps very wide names
            "w-full min-w-[160px]",
          ].join(" ")}
          style={{ maxWidth: "max(100%, 280px)" }}
        >
          {/* Search */}
          {showSearch && (
            <div className="border-b border-white/[0.08] px-2.5 py-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-white/30" />
                <input
                  ref={searchRef}
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Filter columns…"
                  className="w-full rounded-md bg-white/[0.07] py-1.5 pl-7 pr-3 text-xs text-white placeholder:text-white/25 focus:outline-none focus:ring-1 focus:ring-indigo-500/40"
                />
              </div>
            </div>
          )}

          {/* Options */}
          <div
            className="max-h-60 overflow-y-auto overscroll-contain py-1"
            style={{ scrollbarWidth: "thin", scrollbarColor: "rgba(255,255,255,0.1) transparent" }}
          >
            {filtered.length === 0 ? (
              <p className="px-4 py-5 text-center text-xs text-white/30">
                No match for &ldquo;{search}&rdquo;
              </p>
            ) : (
              filtered.map((opt) => {
                const displayLabel = optionLabels?.[opt] ?? opt;
                const isSelected = opt === value;
                return (
                  <button
                    key={opt}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => select(opt)}
                    className={[
                      "flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors",
                      isSelected
                        ? "bg-indigo-600/20 text-indigo-200"
                        : "text-white/65 hover:bg-white/[0.07] hover:text-white",
                    ].join(" ")}
                  >
                    <span className="flex-1 truncate leading-snug">{displayLabel}</span>
                    {isSelected && (
                      <Check className="h-3 w-3 flex-shrink-0 text-indigo-400" />
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

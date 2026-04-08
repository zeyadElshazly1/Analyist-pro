"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  Search,
  ChevronLeft,
  ChevronRight,
  Hash,
  Type,
  Calendar,
  ToggleLeft,
  AlertCircle,
  Loader2,
  Filter,
  Plus,
  X,
} from "lucide-react";
import {
  getDataTable,
  DataTableColumn,
  DataTableResponse,
  ColumnFilter,
  ColumnFilterOp,
  ApiError,
} from "@/lib/api";

// ── Type helpers ──────────────────────────────────────────────────────────────

const DTYPE_ICON: Record<string, React.ElementType> = {
  integer: Hash,
  float: Hash,
  boolean: ToggleLeft,
  datetime: Calendar,
  text: Type,
};

const DTYPE_BADGE: Record<string, string> = {
  integer:  "text-sky-400 bg-sky-500/10",
  float:    "text-blue-400 bg-blue-500/10",
  boolean:  "text-amber-400 bg-amber-500/10",
  datetime: "text-violet-400 bg-violet-500/10",
  text:     "text-emerald-400 bg-emerald-500/10",
};

/** Operators available per dtype, with human labels */
const OPS_FOR_DTYPE: Record<string, { op: ColumnFilterOp; label: string }[]> = {
  integer: [
    { op: "eq",       label: "=" },
    { op: "neq",      label: "≠" },
    { op: "gt",       label: ">" },
    { op: "gte",      label: "≥" },
    { op: "lt",       label: "<" },
    { op: "lte",      label: "≤" },
    { op: "is_null",  label: "is empty" },
    { op: "not_null", label: "is not empty" },
  ],
  float: [
    { op: "eq",       label: "=" },
    { op: "neq",      label: "≠" },
    { op: "gt",       label: ">" },
    { op: "gte",      label: "≥" },
    { op: "lt",       label: "<" },
    { op: "lte",      label: "≤" },
    { op: "is_null",  label: "is empty" },
    { op: "not_null", label: "is not empty" },
  ],
  text: [
    { op: "contains", label: "contains" },
    { op: "eq",       label: "equals" },
    { op: "neq",      label: "not equals" },
    { op: "is_null",  label: "is empty" },
    { op: "not_null", label: "is not empty" },
  ],
  boolean: [
    { op: "eq",       label: "equals" },
    { op: "is_null",  label: "is empty" },
    { op: "not_null", label: "is not empty" },
  ],
  datetime: [
    { op: "gt",       label: "after" },
    { op: "gte",      label: "on or after" },
    { op: "lt",       label: "before" },
    { op: "lte",      label: "on or before" },
    { op: "is_null",  label: "is empty" },
    { op: "not_null", label: "is not empty" },
  ],
};

const NO_VALUE_OPS: ColumnFilterOp[] = ["is_null", "not_null"];

function opLabel(op: ColumnFilterOp, dtype: string): string {
  return OPS_FOR_DTYPE[dtype]?.find((o) => o.op === op)?.label ?? op;
}

// ── Draft filter row ──────────────────────────────────────────────────────────

interface DraftFilter {
  id: number;
  col: string;
  op: ColumnFilterOp;
  value: string;
}

let _draftId = 0;
function newDraft(col: string, dtype: string): DraftFilter {
  const defaultOp = OPS_FOR_DTYPE[dtype]?.[0]?.op ?? "eq";
  return { id: ++_draftId, col, op: defaultOp, value: "" };
}

interface FilterRowProps {
  draft: DraftFilter;
  columns: DataTableColumn[];
  onChange: (updated: DraftFilter) => void;
  onRemove: () => void;
}

function FilterRow({ draft, columns, onChange, onRemove }: FilterRowProps) {
  const col = columns.find((c) => c.name === draft.col);
  const dtype = col?.dtype ?? "text";
  const ops = OPS_FOR_DTYPE[dtype] ?? OPS_FOR_DTYPE.text;
  const needsValue = !NO_VALUE_OPS.includes(draft.op);

  function handleColChange(name: string) {
    const newDtype = columns.find((c) => c.name === name)?.dtype ?? "text";
    const firstOp = OPS_FOR_DTYPE[newDtype]?.[0]?.op ?? "eq";
    onChange({ ...draft, col: name, op: firstOp, value: "" });
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* Column selector */}
      <select
        value={draft.col}
        onChange={(e) => handleColChange(e.target.value)}
        className="rounded-lg border border-white/10 bg-[#0f1020] px-2 py-1.5 text-xs text-white focus:border-indigo-500/50 focus:outline-none max-w-[160px] truncate"
      >
        {columns.map((c) => (
          <option key={c.name} value={c.name} className="bg-[#0f1020]">
            {c.name}
          </option>
        ))}
      </select>

      {/* Operator selector */}
      <select
        value={draft.op}
        onChange={(e) => onChange({ ...draft, op: e.target.value as ColumnFilterOp, value: "" })}
        className="rounded-lg border border-white/10 bg-[#0f1020] px-2 py-1.5 text-xs text-white focus:border-indigo-500/50 focus:outline-none"
      >
        {ops.map((o) => (
          <option key={o.op} value={o.op} className="bg-[#0f1020]">
            {o.label}
          </option>
        ))}
      </select>

      {/* Value input */}
      {needsValue && (
        <input
          type={dtype === "datetime" ? "date" : dtype === "integer" || dtype === "float" ? "number" : "text"}
          value={draft.value}
          onChange={(e) => onChange({ ...draft, value: e.target.value })}
          placeholder="value…"
          className="rounded-lg border border-white/10 bg-[#0f1020] px-2 py-1.5 text-xs text-white placeholder:text-white/25 focus:border-indigo-500/50 focus:outline-none w-28"
        />
      )}

      {/* Remove */}
      <button
        onClick={onRemove}
        className="rounded-md p-1 text-white/30 hover:text-red-400 hover:bg-red-500/10 transition-colors"
        title="Remove filter"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

// ── Cell value renderer ───────────────────────────────────────────────────────

function CellValue({ value, dtype }: { value: string | number | boolean | null; dtype: string }) {
  if (value === null || value === undefined || value === "") {
    return <span className="text-white/20 italic text-[11px]">null</span>;
  }
  if (dtype === "boolean") {
    const v = String(value).toLowerCase();
    const isTrue = v === "true" || v === "1";
    return (
      <span className={`text-[11px] font-medium ${isTrue ? "text-emerald-400" : "text-rose-400"}`}>
        {isTrue ? "true" : "false"}
      </span>
    );
  }
  if (dtype === "float" && typeof value === "number") {
    return <span className="tabular-nums">{value.toLocaleString(undefined, { maximumFractionDigits: 4 })}</span>;
  }
  if (dtype === "integer" && typeof value === "number") {
    return <span className="tabular-nums">{value.toLocaleString()}</span>;
  }
  const str = String(value);
  if (str.length > 60) return <span title={str}>{str.slice(0, 58)}…</span>;
  return <span>{str}</span>;
}

// ── Sort indicator ────────────────────────────────────────────────────────────

function SortIndicator({ col, sortCol, sortDir }: { col: string; sortCol: string | null; sortDir: "asc" | "desc" }) {
  if (col !== sortCol) return <ChevronsUpDown className="h-3 w-3 text-white/20" />;
  return sortDir === "asc"
    ? <ChevronUp className="h-3 w-3 text-indigo-400" />
    : <ChevronDown className="h-3 w-3 text-indigo-400" />;
}

// ── Column header stats ───────────────────────────────────────────────────────

function ColStats({ col }: { col: DataTableColumn }) {
  return (
    <div className="mt-1 flex items-center gap-2">
      {col.null_pct > 0 && (
        <span className={`text-[10px] ${col.null_pct > 20 ? "text-amber-400" : "text-white/30"}`}>
          {col.null_pct}% null
        </span>
      )}
      <span className="text-[10px] text-white/25">{col.unique_count.toLocaleString()} unique</span>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

interface Props {
  projectId: number;
}

export function DataTableView({ projectId }: Props) {
  const [data, setData] = useState<DataTableResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Pagination / sort / search
  const [page, setPage] = useState(1);
  const [perPage] = useState(50);
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Column filters
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [drafts, setDrafts] = useState<DraftFilter[]>([]);
  // Applied filters — only updated when user clicks "Apply"
  const [appliedFilters, setAppliedFilters] = useState<ColumnFilter[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getDataTable(projectId, {
        page,
        perPage,
        sortCol: sortCol ?? undefined,
        sortDir,
        search: search || undefined,
        columnFilters: appliedFilters.length > 0 ? appliedFilters : undefined,
      });
      setData(result);
    } catch (e) {
      setError(e instanceof ApiError ? e.userMessage : "Failed to load data.");
    } finally {
      setLoading(false);
    }
  }, [projectId, page, perPage, sortCol, sortDir, search, appliedFilters]);

  useEffect(() => { load(); }, [load]);

  // Debounce search
  function handleSearchInput(val: string) {
    setSearchInput(val);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setSearch(val);
      setPage(1);
    }, 350);
  }

  function handleSort(col: string) {
    if (sortCol === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
    setPage(1);
  }

  // ── Filter management ──────────────────────────────────────────────────────

  const columns = data?.columns ?? [];

  function openFilters() {
    // Pre-populate drafts from applied filters, or start fresh
    if (drafts.length === 0 && appliedFilters.length > 0) {
      setDrafts(appliedFilters.map((f) => ({ ...f, id: ++_draftId })));
    } else if (drafts.length === 0 && columns.length > 0) {
      setDrafts([newDraft(columns[0].name, columns[0].dtype)]);
    }
    setFiltersOpen((o) => !o);
  }

  function addDraftRow() {
    if (columns.length === 0) return;
    setDrafts((prev) => [...prev, newDraft(columns[0].name, columns[0].dtype)]);
  }

  function updateDraft(id: number, updated: DraftFilter) {
    setDrafts((prev) => prev.map((d) => (d.id === id ? updated : d)));
  }

  function removeDraft(id: number) {
    setDrafts((prev) => prev.filter((d) => d.id !== id));
  }

  function applyFilters() {
    const valid: ColumnFilter[] = drafts
      .filter((d) => d.col && d.op && (NO_VALUE_OPS.includes(d.op) || d.value.trim() !== ""))
      .map(({ col, op, value }) => ({ col, op, value }));
    setAppliedFilters(valid);
    setPage(1);
    setFiltersOpen(false);
  }

  function clearAllFilters() {
    setAppliedFilters([]);
    setDrafts([]);
    setPage(1);
    setFiltersOpen(false);
  }

  function removeAppliedFilter(idx: number) {
    setAppliedFilters((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      setDrafts(next.map((f) => ({ ...f, id: ++_draftId })));
      return next;
    });
    setPage(1);
  }

  // ── Error state ────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <AlertCircle className="h-8 w-8 text-red-400/60" />
        <p className="text-sm text-red-400">{error}</p>
        <button
          onClick={load}
          className="mt-1 rounded-lg bg-white/5 px-4 py-2 text-xs text-white/60 hover:text-white transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  const hasActiveFilters = appliedFilters.length > 0;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-3">

      {/* ── Controls bar ───────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Global search */}
        <div className="relative flex-1 min-w-0 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-white/30" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => handleSearchInput(e.target.value)}
            placeholder="Search all text columns…"
            className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] py-2 pl-9 pr-3 text-sm text-white placeholder:text-white/25 focus:border-indigo-500/50 focus:outline-none focus:ring-1 focus:ring-indigo-500/30 transition-colors"
          />
        </div>

        {/* Filter toggle button */}
        <button
          onClick={openFilters}
          className={`flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
            hasActiveFilters || filtersOpen
              ? "border-indigo-500/50 bg-indigo-600/15 text-indigo-300"
              : "border-white/[0.08] bg-white/[0.03] text-white/50 hover:text-white hover:border-white/20"
          }`}
        >
          <Filter className="h-3.5 w-3.5" />
          Filters
          {hasActiveFilters && (
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-bold text-white">
              {appliedFilters.length}
            </span>
          )}
        </button>

        {/* Row count */}
        {data && (
          <p className="ml-auto text-xs text-white/35 whitespace-nowrap">
            {loading ? "…" : `${data.total_rows.toLocaleString()} rows`}
            {(data.search || hasActiveFilters) ? " · filtered" : ""}
          </p>
        )}
      </div>

      {/* ── Active filter chips ─────────────────────────────────────────────── */}
      {hasActiveFilters && (
        <div className="flex flex-wrap items-center gap-2">
          {appliedFilters.map((f, i) => {
            const dtype = columns.find((c) => c.name === f.col)?.dtype ?? "text";
            const label = NO_VALUE_OPS.includes(f.op)
              ? `${f.col} ${opLabel(f.op, dtype)}`
              : `${f.col} ${opLabel(f.op, dtype)} ${f.value}`;
            return (
              <span
                key={i}
                className="flex items-center gap-1.5 rounded-full border border-indigo-500/30 bg-indigo-600/10 px-2.5 py-1 text-[11px] text-indigo-300"
              >
                {label}
                <button
                  onClick={() => removeAppliedFilter(i)}
                  className="rounded-full text-indigo-400/60 hover:text-indigo-300 transition-colors"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            );
          })}
          <button
            onClick={clearAllFilters}
            className="text-[11px] text-white/30 hover:text-red-400 transition-colors"
          >
            Clear all
          </button>
        </div>
      )}

      {/* ── Filter builder panel ────────────────────────────────────────────── */}
      {filtersOpen && columns.length > 0 && (
        <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-4 space-y-3">
          <p className="text-xs font-semibold text-white/60 uppercase tracking-wider">Column filters</p>

          {drafts.length === 0 && (
            <p className="text-xs text-white/30">No filters added yet.</p>
          )}

          <div className="space-y-2.5">
            {drafts.map((draft) => (
              <FilterRow
                key={draft.id}
                draft={draft}
                columns={columns}
                onChange={(updated) => updateDraft(draft.id, updated)}
                onRemove={() => removeDraft(draft.id)}
              />
            ))}
          </div>

          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={addDraftRow}
              className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/50 hover:text-white hover:border-white/20 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              Add filter
            </button>
            <button
              onClick={applyFilters}
              className="rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
            >
              Apply
            </button>
            <button
              onClick={() => setFiltersOpen(false)}
              className="text-xs text-white/30 hover:text-white/60 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* ── Table ──────────────────────────────────────────────────────────── */}
      <div className="relative rounded-xl border border-white/[0.07] bg-[#080812] overflow-hidden">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-[#080812]/70 backdrop-blur-[1px]">
            <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full min-w-max text-sm border-collapse">
            <thead>
              <tr className="border-b border-white/[0.07]">
                <th className="sticky left-0 z-10 bg-[#080812] px-3 py-3 text-right text-[10px] text-white/20 font-normal select-none w-12">
                  #
                </th>
                {(data?.columns ?? []).map((col) => {
                  const Icon = DTYPE_ICON[col.dtype] ?? Type;
                  return (
                    <th
                      key={col.name}
                      onClick={() => handleSort(col.name)}
                      className="cursor-pointer select-none px-4 py-3 text-left align-top hover:bg-white/[0.03] transition-colors group"
                    >
                      <div className="flex items-center gap-1.5 whitespace-nowrap">
                        <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${DTYPE_BADGE[col.dtype]}`}>
                          <Icon className="h-2.5 w-2.5" />
                          {col.dtype}
                        </span>
                        <span className="text-xs font-medium text-white/80 group-hover:text-white transition-colors">
                          {col.name}
                        </span>
                        <SortIndicator col={col.name} sortCol={sortCol} sortDir={sortDir} />
                      </div>
                      <ColStats col={col} />
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {!loading && (data?.rows ?? []).length === 0 && (
                <tr>
                  <td
                    colSpan={(data?.columns.length ?? 0) + 1}
                    className="py-12 text-center text-sm text-white/30"
                  >
                    {search || hasActiveFilters
                      ? "No rows match your filters."
                      : "No data."}
                  </td>
                </tr>
              )}
              {(data?.rows ?? []).map((row, i) => {
                const globalIdx =
                  ((data?.page ?? 1) - 1) * (data?.per_page ?? 50) + i + 1;
                return (
                  <tr
                    key={i}
                    className="border-t border-white/[0.04] hover:bg-white/[0.025] transition-colors"
                  >
                    <td className="sticky left-0 z-10 bg-[#080812] px-3 py-2.5 text-right text-[10px] text-white/20 tabular-nums select-none">
                      {globalIdx}
                    </td>
                    {row.map((cell, j) => (
                      <td
                        key={j}
                        className="px-4 py-2.5 text-xs text-white/70 whitespace-nowrap max-w-[220px] overflow-hidden text-ellipsis"
                      >
                        <CellValue
                          value={cell}
                          dtype={data?.columns[j]?.dtype ?? "text"}
                        />
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Pagination ─────────────────────────────────────────────────────── */}
      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-between text-xs text-white/40">
          <span>
            Page {data.page} of {data.total_pages.toLocaleString()}
            {" · "}
            {Math.min(data.per_page, data.total_rows - (data.page - 1) * data.per_page)} of{" "}
            {data.total_rows.toLocaleString()} rows
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(1)}
              disabled={page <= 1 || loading}
              className="rounded-md px-2 py-1 text-white/40 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              ««
            </button>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="rounded-md p-1 text-white/40 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
              disabled={page >= data.total_pages || loading}
              className="rounded-md p-1 text-white/40 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => setPage(data.total_pages)}
              disabled={page >= data.total_pages || loading}
              className="rounded-md px-2 py-1 text-white/40 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              »»
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

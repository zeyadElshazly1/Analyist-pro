/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useState, useEffect } from "react";
import { getProjects, getJoinColumns, runJoin } from "@/lib/api";
import { Merge, Loader2, GitMerge } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = { currentProjectId: number };

type JoinResult = {
  rows: number;
  left_rows: number;
  right_rows: number;
  columns: string[];
  how: string;
  left_on: string;
  right_on: string;
  preview: Record<string, string>[];
};

const HOW_OPTIONS = [
  { value: "inner", label: "Inner — matching rows only" },
  { value: "left",  label: "Left — all left rows" },
  { value: "right", label: "Right — all right rows" },
  { value: "outer", label: "Outer — all rows from both" },
] as const;

export function JoinView({ currentProjectId }: Props) {
  const [projects, setProjects] = useState<{ id: number; name: string }[]>([]);
  const [rightProjectId, setRightProjectId] = useState<number | "">("");
  const [leftCols, setLeftCols] = useState<string[]>([]);
  const [rightCols, setRightCols] = useState<string[]>([]);
  const [leftOn, setLeftOn] = useState("");
  const [rightOn, setRightOn] = useState("");
  const [how, setHow] = useState<"inner" | "left" | "right" | "outer">("inner");
  const [loadingCols, setLoadingCols] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<JoinResult | null>(null);
  const [error, setError] = useState("");

  // Load other projects to pick the right-hand side
  useEffect(() => {
    getProjects()
      .then((data: any) => {
        const others = (data || []).filter((p: any) => p.id !== currentProjectId);
        setProjects(others);
      })
      .catch(() => {});
  }, [currentProjectId]);

  // When right project changes, load column options
  useEffect(() => {
    if (!rightProjectId) return;
    setLoadingCols(true);
    setLeftCols([]);
    setRightCols([]);
    setLeftOn("");
    setRightOn("");
    setResult(null);
    setError("");
    getJoinColumns(currentProjectId, rightProjectId as number)
      .then((data) => {
        setLeftCols(data.left_columns);
        setRightCols(data.right_columns);
        // Pre-select first suggested key if any
        const suggested = data.suggested_join_keys;
        if (suggested.length > 0) {
          setLeftOn(suggested[0]);
          setRightOn(suggested[0]);
        } else {
          setLeftOn(data.left_columns[0] ?? "");
          setRightOn(data.right_columns[0] ?? "");
        }
      })
      .catch((e: any) => setError(e.message || "Failed to load columns."))
      .finally(() => setLoadingCols(false));
  }, [rightProjectId, currentProjectId]);

  async function handleJoin() {
    if (!rightProjectId || !leftOn || !rightOn) return;
    setError("");
    setResult(null);
    setRunning(true);
    try {
      const res = await runJoin(currentProjectId, rightProjectId as number, leftOn, rightOn, how);
      setResult(res);
    } catch (e: any) {
      setError(e.message || "Join failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1 flex items-center gap-2">
          <GitMerge className="h-5 w-5 text-indigo-400" />
          Join Datasets
        </h2>
        <p className="text-sm text-white/50">
          Merge this project&apos;s data with another project on a common key.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Right-side project selector */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-xs font-medium text-white/60">
            Right dataset (other project)
          </label>
          <select
            value={rightProjectId}
            onChange={(e) => setRightProjectId(e.target.value ? Number(e.target.value) : "")}
            className="w-full rounded-lg bg-white/[0.05] border border-white/[0.08] px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500/50"
          >
            <option value="">— pick a project —</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          {projects.length === 0 && (
            <p className="mt-1 text-xs text-white/30">
              Create another project with uploaded data to enable joining.
            </p>
          )}
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-medium text-white/60">Join type</label>
          <select
            value={how}
            onChange={(e) => setHow(e.target.value as typeof how)}
            className="w-full rounded-lg bg-white/[0.05] border border-white/[0.08] px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500/50"
          >
            {HOW_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Join key selectors — shown after right project is chosen */}
      {rightProjectId && (
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-white/60">
              Left key (this project)
            </label>
            {loadingCols ? (
              <div className="flex items-center gap-2 text-xs text-white/40">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading columns…
              </div>
            ) : (
              <select
                value={leftOn}
                onChange={(e) => setLeftOn(e.target.value)}
                className="w-full rounded-lg bg-white/[0.05] border border-white/[0.08] px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500/50"
              >
                <option value="">— select column —</option>
                {leftCols.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            )}
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-white/60">
              Right key (other project)
            </label>
            {loadingCols ? (
              <div className="flex items-center gap-2 text-xs text-white/40">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading columns…
              </div>
            ) : (
              <select
                value={rightOn}
                onChange={(e) => setRightOn(e.target.value)}
                className="w-full rounded-lg bg-white/[0.05] border border-white/[0.08] px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500/50"
              >
                <option value="">— select column —</option>
                {rightCols.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            )}
          </div>
        </div>
      )}

      <Button
        onClick={handleJoin}
        disabled={running || !rightProjectId || !leftOn || !rightOn}
        className="bg-indigo-600 hover:bg-indigo-500 text-white gap-2"
      >
        {running ? (
          <><Loader2 className="h-4 w-4 animate-spin" />Joining…</>
        ) : (
          <><Merge className="h-4 w-4" />Run Join</>
        )}
      </Button>

      {/* Result */}
      {result && (
        <div className="space-y-4">
          {/* Stats row */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg border border-white/[0.07] bg-white/[0.03] p-4 text-center">
              <div className="text-2xl font-bold text-indigo-400">{result.left_rows.toLocaleString()}</div>
              <div className="text-xs text-white/50 mt-1">Left rows</div>
            </div>
            <div className="rounded-lg border border-white/[0.07] bg-white/[0.03] p-4 text-center">
              <div className="text-2xl font-bold text-indigo-400">{result.right_rows.toLocaleString()}</div>
              <div className="text-xs text-white/50 mt-1">Right rows</div>
            </div>
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4 text-center">
              <div className="text-2xl font-bold text-emerald-400">{result.rows.toLocaleString()}</div>
              <div className="text-xs text-white/50 mt-1">Joined rows</div>
            </div>
          </div>

          <p className="text-xs text-white/40">
            <span className="capitalize">{result.how}</span> join on{" "}
            <code className="rounded bg-white/[0.06] px-1 py-0.5">{result.left_on}</code> ={" "}
            <code className="rounded bg-white/[0.06] px-1 py-0.5">{result.right_on}</code> ·{" "}
            {result.columns.length} columns
          </p>

          {/* Preview table */}
          <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/[0.07] bg-white/[0.02]">
                  {result.columns.slice(0, 12).map((col) => (
                    <th
                      key={col}
                      className="whitespace-nowrap px-3 py-2 text-left text-white/50 font-medium"
                    >
                      {col}
                    </th>
                  ))}
                  {result.columns.length > 12 && (
                    <th className="px-3 py-2 text-left text-white/30 font-medium">
                      +{result.columns.length - 12} more…
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {result.preview.slice(0, 50).map((row, i) => (
                  <tr key={i} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                    {result.columns.slice(0, 12).map((col) => (
                      <td key={col} className="whitespace-nowrap px-3 py-2 text-white/70 max-w-[160px] truncate">
                        {row[col] ?? ""}
                      </td>
                    ))}
                    {result.columns.length > 12 && <td />}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.preview.length < result.rows && (
            <p className="text-center text-xs text-white/30">
              Showing first {result.preview.length} of {result.rows.toLocaleString()} rows
            </p>
          )}
        </div>
      )}
    </div>
  );
}

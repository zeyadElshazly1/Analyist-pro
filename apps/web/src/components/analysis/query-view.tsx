/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useState, useEffect, useRef } from "react";
import { executeQuery, getQuerySchema } from "@/lib/api";
import { Loader2, Terminal, Download, HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = { projectId: number };

const EXAMPLE_QUERIES = [
  "SELECT * FROM data LIMIT 10",
  "SELECT COUNT(*) as total_rows FROM data",
  "SELECT * FROM data ORDER BY RANDOM() LIMIT 5",
];

export function QueryView({ projectId }: Props) {
  const [sql, setSql] = useState("SELECT * FROM data LIMIT 10");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [schema, setSchema] = useState<any[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    getQuerySchema(projectId).then((data: any) => setSchema(data.columns || [])).catch(() => {});
  }, [projectId]);

  async function handleRun() {
    if (!sql.trim()) { setError("Enter a SQL query."); return; }
    setLoading(true); setError("");
    try {
      const data = await executeQuery(projectId, sql) as any;
      setResult(data);
    } catch (e: any) {
      try { const parsed = JSON.parse(e.message); setError(parsed.detail || e.message); }
      catch { setError(e.message || "Query failed."); }
    } finally { setLoading(false); }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      handleRun();
    }
  }

  function downloadCsv() {
    if (!result?.rows?.length) return;
    const headers = result.columns.join(",");
    const rows = result.rows.map((row: any) =>
      result.columns.map((col: string) => {
        const v = row[col];
        if (v == null) return "";
        if (typeof v === "string" && (v.includes(",") || v.includes('"'))) return `"${v.replace(/"/g, '""')}"`;
        return String(v);
      }).join(",")
    );
    const csv = [headers, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `query_result.csv`; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1 flex items-center gap-2">
          <Terminal className="h-5 w-5 text-indigo-400" /> SQL Query Engine
        </h2>
        <p className="text-sm text-white/50">Run SQL queries on your dataset. The table is available as <code className="text-indigo-400">data</code>.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Schema sidebar */}
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
          <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-3">Schema: data</h3>
          <div className="space-y-1 max-h-[300px] overflow-y-auto">
            {schema.map((col) => (
              <div key={col.name} className="group cursor-pointer rounded px-2 py-1 hover:bg-white/[0.05]"
                onClick={() => {
                  const ta = textareaRef.current;
                  if (ta) {
                    const pos = ta.selectionStart;
                    const newVal = sql.slice(0, pos) + col.name + sql.slice(pos);
                    setSql(newVal);
                    ta.focus();
                  }
                }}>
                <div className="text-xs text-white/70 font-medium">{col.name}</div>
                <div className="text-xs text-white/30">{col.dtype}</div>
              </div>
            ))}
          </div>

          <div className="mt-4">
            <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">Examples</h3>
            {EXAMPLE_QUERIES.map((q) => (
              <button key={q} onClick={() => setSql(q)}
                className="block w-full text-left text-xs text-indigo-400 hover:text-indigo-300 py-1 truncate">
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Editor + results */}
        <div className="lg:col-span-3 space-y-4">
          {error && <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</div>}

          <div className="rounded-xl border border-white/[0.07] bg-[#0d1117] overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 bg-white/[0.03] border-b border-white/[0.07]">
              <span className="text-xs text-white/40">SQL Editor (Ctrl+Enter to run)</span>
              <HelpCircle className="h-3.5 w-3.5 text-white/20" />
            </div>
            <textarea
              ref={textareaRef}
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full bg-transparent text-sm text-green-300 font-mono p-4 focus:outline-none resize-none min-h-[140px]"
              spellCheck={false}
            />
          </div>

          <div className="flex gap-2">
            <Button onClick={handleRun} disabled={loading} className="bg-indigo-600 hover:bg-indigo-500 text-white gap-2">
              {loading ? <><Loader2 className="h-4 w-4 animate-spin" />Running…</> : <><Terminal className="h-4 w-4" />Run Query</>}
            </Button>
            {result?.rows?.length > 0 && (
              <Button onClick={downloadCsv} variant="outline" className="border-white/10 text-white/70 hover:text-white gap-2">
                <Download className="h-4 w-4" /> Export CSV
              </Button>
            )}
          </div>

          {result && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-white/50">
                  {result.row_count} row{result.row_count !== 1 ? "s" : ""}
                  {result.truncated ? ` (showing first 500)` : ""}
                  · {result.execution_time_ms}ms
                </span>
              </div>
              <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] overflow-auto max-h-[400px]">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-[#0f172a]">
                    <tr>
                      {(result.columns || []).map((col: string) => (
                        <th key={col} className="px-3 py-2 text-left text-white/50 font-medium border-b border-white/[0.07] whitespace-nowrap">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(result.rows || []).map((row: any, ri: number) => (
                      <tr key={ri} className="border-b border-white/[0.04]">
                        {(result.columns || []).map((col: string) => (
                          <td key={col} className="px-3 py-2 text-white/70 whitespace-nowrap max-w-[200px] truncate">
                            {row[col] == null ? <span className="text-white/20">null</span> : String(row[col])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

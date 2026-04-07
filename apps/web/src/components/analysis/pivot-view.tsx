/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useState, useEffect } from "react";
import { getPivotColumns, runPivot } from "@/lib/api";
import { ColumnSelect } from "@/components/ui/column-select";
import { Loader2, Table2 } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = { projectId: number };

export function PivotView({ projectId }: Props) {
  const [allCols, setAllCols] = useState<string[]>([]);
  const [rows, setRows] = useState<string[]>([]);
  const [cols, setCols] = useState<string[]>([]);
  const [values, setValues] = useState("");
  const [aggfunc, setAggfunc] = useState("sum");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getPivotColumns(projectId)
      .then((data: any) => {
        const all: string[] = data.all_columns || [];
        setAllCols(all);
        if (all.length > 0) setValues(all[0]);
      })
      .catch(() => setError("Failed to load columns."));
  }, [projectId]);

  async function handleRun() {
    if (!rows.length || !values) { setError("Select at least one row field and a values field."); return; }
    setLoading(true);
    setError("");
    try {
      const data = await runPivot(projectId, rows, cols, values, aggfunc);
      setResult(data);
    } catch (e: any) {
      try { const p = JSON.parse(e.message); setError(p.detail || e.message); }
      catch { setError(e.message || "Pivot failed."); }
    } finally {
      setLoading(false);
    }
  }

  function toggleCol(col: string, selected: string[], setter: (v: string[]) => void) {
    setter(selected.includes(col) ? selected.filter((c) => c !== col) : [...selected, col]);
  }

  function cellBg(value: number, max: number): string {
    const ratio = max > 0 ? Math.abs(value) / max : 0;
    return `rgba(99,102,241,${(ratio * 0.45).toFixed(2)})`;
  }

  const flatNums = (result?.pivot_data || []).flat().filter((v: any) => typeof v === "number" && !isNaN(v));
  const maxVal: number = flatNums.length > 0 ? Math.max(...flatNums) : 0;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1 flex items-center gap-2">
          <Table2 className="h-5 w-5 text-indigo-400" /> Pivot Table
        </h2>
        <p className="text-sm text-white/50">Build dynamic pivot tables from any columns.</p>
      </div>

      {error && <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-white/50 mb-2 uppercase tracking-wider">Row Fields</label>
          <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3 max-h-44 overflow-y-auto space-y-1">
            {allCols.length === 0
              ? <span className="text-xs text-white/30">Loading…</span>
              : allCols.map((c) => (
                <label key={c} className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={rows.includes(c)} onChange={() => toggleCol(c, rows, setRows)} className="accent-indigo-500" />
                  <span className="text-sm text-white/70">{c}</span>
                </label>
              ))}
          </div>
        </div>

        <div>
          <label className="block text-xs text-white/50 mb-2 uppercase tracking-wider">Column Fields (optional)</label>
          <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3 max-h-44 overflow-y-auto space-y-1">
            {allCols.length === 0
              ? <span className="text-xs text-white/30">Loading…</span>
              : allCols.map((c) => (
                <label key={c} className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={cols.includes(c)} onChange={() => toggleCol(c, cols, setCols)} className="accent-indigo-500" />
                  <span className="text-sm text-white/70">{c}</span>
                </label>
              ))}
          </div>
        </div>

        <ColumnSelect
          label="Values Column"
          value={values}
          options={allCols}
          onChange={setValues}
        />

        <ColumnSelect
          label="Aggregation"
          value={aggfunc}
          options={["sum", "mean", "count", "median", "min", "max", "std"]}
          optionLabels={{ sum: "Sum", mean: "Mean", count: "Count", median: "Median", min: "Min", max: "Max", std: "Std Dev" }}
          onChange={setAggfunc}
        />
      </div>

      <Button onClick={handleRun} disabled={loading} className="bg-indigo-600 hover:bg-indigo-500 text-white gap-2">
        {loading ? <><Loader2 className="h-4 w-4 animate-spin" />Building…</> : "Build Pivot Table"}
      </Button>

      {result && (
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] overflow-auto max-h-[500px]">
          <table className="w-full text-xs border-collapse">
            <thead className="sticky top-0 bg-[#0f172a] z-10">
              <tr>
                <th className="px-3 py-2 text-left text-white/50 font-medium border-b border-white/[0.07] min-w-[120px]">Row</th>
                {(result.col_labels || []).map((cl: string) => (
                  <th key={cl} className={`px-3 py-2 text-right text-white/50 font-medium border-b border-white/[0.07] min-w-[80px] ${cl === "All" || cl === "Grand Total" ? "text-indigo-400" : ""}`}>{cl}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(result.row_labels || []).map((rl: string, ri: number) => (
                <tr key={ri} className={`border-b border-white/[0.04] ${rl === "Grand Total" ? "bg-white/[0.04] font-semibold text-indigo-300" : ""}`}>
                  <td className="px-3 py-2 text-white/70 font-medium whitespace-nowrap">{rl}</td>
                  {(result.pivot_data[ri] || []).map((val: any, ci: number) => {
                    const isTotal = rl === "Grand Total" || result.col_labels?.[ci] === "All";
                    return (
                      <td
                        key={ci}
                        className="px-3 py-2 text-right text-white/80 whitespace-nowrap"
                        style={!isTotal && typeof val === "number" ? { background: cellBg(val, maxVal) } : {}}
                      >
                        {typeof val === "number" ? val.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(val ?? "—")}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

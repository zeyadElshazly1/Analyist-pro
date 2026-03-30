"use client";

import { useState } from "react";
import { trainModel, getMlColumns } from "@/lib/api";
import { Loader2, Brain, TrendingUp, BarChart2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  CartesianGrid,
  Cell,
} from "recharts";

type Props = { projectId: number };

export function PredictionsView({ projectId }: Props) {
  const [columns, setColumns] = useState<string[]>([]);
  const [targetCol, setTargetCol] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingCols, setLoadingCols] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [colsLoaded, setColsLoaded] = useState(false);

  async function loadColumns() {
    if (colsLoaded) return;
    setLoadingCols(true);
    try {
      const data = await getMlColumns(projectId);
      setColumns(data.columns || []);
      setColsLoaded(true);
    } catch (e) {
      setError("Failed to load columns.");
    } finally {
      setLoadingCols(false);
    }
  }

  async function handleTrain() {
    if (!targetCol) { setError("Select a target column."); return; }
    setLoading(true);
    setError("");
    try {
      const data = await trainModel(projectId, targetCol);
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Training failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1 flex items-center gap-2">
          <Brain className="h-5 w-5 text-indigo-400" /> AutoML Predictions
        </h2>
        <p className="text-sm text-white/50">Train 4 ML models and compare them. Select what you want to predict.</p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</div>
      )}

      <div className="flex gap-3 items-end flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs text-white/50 mb-1">What do you want to predict?</label>
          <select
            className="w-full rounded-lg bg-white/[0.05] border border-white/10 px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
            value={targetCol}
            onChange={(e) => setTargetCol(e.target.value)}
            onFocus={loadColumns}
          >
            <option value="">Select a column…</option>
            {columns.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <Button
          onClick={handleTrain}
          disabled={loading || !targetCol}
          className="bg-indigo-600 hover:bg-indigo-500 text-white gap-2"
        >
          {loading ? <><Loader2 className="h-4 w-4 animate-spin" />Training…</> : <><TrendingUp className="h-4 w-4" />Train Models</>}
        </Button>
      </div>

      {result && (
        <div className="space-y-6">
          {/* Summary */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-white/[0.03] border border-white/[0.07] p-4 text-center">
              <div className="text-2xl font-bold text-indigo-400">{result.n_rows?.toLocaleString()}</div>
              <div className="text-xs text-white/50 mt-1">Training Rows</div>
            </div>
            <div className="rounded-lg bg-white/[0.03] border border-white/[0.07] p-4 text-center">
              <div className="text-2xl font-bold text-indigo-400">{result.n_features}</div>
              <div className="text-xs text-white/50 mt-1">Features Used</div>
            </div>
            <div className="rounded-lg bg-white/[0.03] border border-white/[0.07] p-4 text-center">
              <div className="text-xl font-bold text-indigo-400 capitalize">{result.problem_type}</div>
              <div className="text-xs text-white/50 mt-1">Problem Type</div>
            </div>
          </div>

          {/* Model leaderboard */}
          <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5">
            <h3 className="text-sm font-semibold text-white/70 uppercase tracking-wider mb-4">Model Leaderboard</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.07]">
                    <th className="text-left py-2 pr-4 text-white/50 font-medium">Model</th>
                    {result.problem_type === "regression" ? (
                      <>
                        <th className="text-right py-2 pr-4 text-white/50 font-medium">R²</th>
                        <th className="text-right py-2 pr-4 text-white/50 font-medium">RMSE</th>
                        <th className="text-right py-2 pr-4 text-white/50 font-medium">MAE</th>
                      </>
                    ) : (
                      <>
                        <th className="text-right py-2 pr-4 text-white/50 font-medium">F1</th>
                        <th className="text-right py-2 pr-4 text-white/50 font-medium">Accuracy</th>
                        <th className="text-right py-2 pr-4 text-white/50 font-medium">AUC</th>
                      </>
                    )}
                    <th className="text-right py-2 text-white/50 font-medium">CV Score</th>
                  </tr>
                </thead>
                <tbody>
                  {(result.models || []).filter((m: any) => !m.error).map((m: any) => (
                    <tr key={m.name} className={`border-b border-white/[0.04] ${m.name === result.best_model ? "text-indigo-300" : "text-white/70"}`}>
                      <td className="py-2 pr-4 font-medium">
                        {m.name === result.best_model && <span className="mr-1 text-indigo-400">★</span>}
                        {m.name}
                      </td>
                      {result.problem_type === "regression" ? (
                        <>
                          <td className="text-right py-2 pr-4">{m.r2 != null ? m.r2.toFixed(3) : "—"}</td>
                          <td className="text-right py-2 pr-4">{m.rmse != null ? m.rmse.toFixed(3) : "—"}</td>
                          <td className="text-right py-2 pr-4">{m.mae != null ? m.mae.toFixed(3) : "—"}</td>
                        </>
                      ) : (
                        <>
                          <td className="text-right py-2 pr-4">{m.f1 != null ? m.f1.toFixed(3) : "—"}</td>
                          <td className="text-right py-2 pr-4">{m.accuracy != null ? m.accuracy.toFixed(3) : "—"}</td>
                          <td className="text-right py-2 pr-4">{m.auc != null ? m.auc.toFixed(3) : "—"}</td>
                        </>
                      )}
                      <td className="text-right py-2">{m.cv_score != null ? `${m.cv_score.toFixed(3)} ± ${(m.cv_std || 0).toFixed(3)}` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Feature importance */}
          {result.feature_importance?.length > 0 && (
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5">
              <h3 className="text-sm font-semibold text-white/70 uppercase tracking-wider mb-4">Feature Importance</h3>
              <ResponsiveContainer width="100%" height={Math.min(result.feature_importance.length * 30 + 20, 350)}>
                <BarChart data={result.feature_importance.slice(0, 12)} layout="vertical" margin={{ left: 10 }}>
                  <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                  <YAxis dataKey="feature" type="category" tick={{ fill: "#94a3b8", fontSize: 11 }} width={120} />
                  <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }} />
                  <Bar dataKey="importance" radius={4}>
                    {result.feature_importance.slice(0, 12).map((_: any, i: number) => (
                      <Cell key={i} fill={i === 0 ? "#6366f1" : "#4f46e5"} fillOpacity={1 - i * 0.05} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Preprocessing notes */}
          {result.preprocessing_notes?.length > 0 && (
            <div className="rounded-lg bg-white/[0.03] border border-white/[0.07] p-4">
              <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">Preprocessing</h3>
              <ul className="text-sm text-white/60 space-y-1">
                {result.preprocessing_notes.map((note: string, i: number) => (
                  <li key={i}>· {note}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useState, useEffect } from "react";
import { trainModel, getMlColumns, getModelInfo, predictRows } from "@/lib/api";
import { ColumnSelect } from "@/components/ui/column-select";
import { Loader2, Brain, TrendingUp, FlaskConical } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

type Props = { projectId: number };

const DARK_TOOLTIP = {
  contentStyle: {
    background: "#111118",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 8,
    color: "#fff",
  },
};

export function PredictionsView({ projectId }: Props) {
  const [columns, setColumns] = useState<string[]>([]);
  const [targetCol, setTargetCol] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  // Predict panel
  const [modelInfo, setModelInfo] = useState<any>(null);
  const [predictJson, setPredictJson] = useState("");
  const [predictLoading, setPredictLoading] = useState(false);
  const [predictError, setPredictError] = useState("");
  const [predictResult, setPredictResult] = useState<any>(null);

  useEffect(() => {
    getMlColumns(projectId)
      .then((data: any) => {
        const cols: string[] = data.columns || [];
        setColumns(cols);
        if (cols.length > 0) setTargetCol(cols[cols.length - 1]);
      })
      .catch(() => setError("Failed to load columns."));
    // Try loading saved model info
    getModelInfo(projectId)
      .then((info) => {
        setModelInfo(info);
        // Pre-fill predict JSON with a blank row using feature columns
        const blank: Record<string, string> = {};
        info.feature_names.forEach((f: string) => { blank[f] = ""; });
        setPredictJson(JSON.stringify([blank], null, 2));
      })
      .catch(() => { /* no model yet — that's fine */ });
  }, [projectId]);

  async function handleTrain() {
    if (!targetCol) { setError("Select a target column."); return; }
    setLoading(true);
    setError("");
    try {
      const data = await trainModel(projectId, targetCol);
      setResult(data);
      // Refresh model info + pre-fill predict JSON
      getModelInfo(projectId).then((info) => {
        setModelInfo(info);
        const blank: Record<string, string> = {};
        info.feature_names.forEach((f: string) => { blank[f] = ""; });
        setPredictJson(JSON.stringify([blank], null, 2));
        setPredictResult(null);
      }).catch(() => {});
    } catch (e: any) {
      try { const p = JSON.parse(e.message); setError(p.detail || e.message); }
      catch { setError(e.message || "Training failed."); }
    } finally {
      setLoading(false);
    }
  }

  async function handlePredict() {
    setPredictError("");
    setPredictResult(null);
    let rows: Record<string, unknown>[];
    try {
      rows = JSON.parse(predictJson);
      if (!Array.isArray(rows)) rows = [rows];
    } catch {
      setPredictError("Invalid JSON. Paste a JSON array of row objects.");
      return;
    }
    setPredictLoading(true);
    try {
      const res = await predictRows(projectId, rows);
      setPredictResult(res);
    } catch (e: any) {
      setPredictError(e.message || "Prediction failed.");
    } finally {
      setPredictLoading(false);
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
        <ColumnSelect
          label="What do you want to predict?"
          value={targetCol}
          options={columns}
          onChange={setTargetCol}
          className="flex-1 min-w-[200px]"
        />
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
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-white/[0.03] border border-white/[0.07] p-4 text-center">
              <div className="text-2xl font-bold text-indigo-400">{(result.n_rows || 0).toLocaleString()}</div>
              <div className="text-xs text-white/50 mt-1">Training Rows</div>
            </div>
            <div className="rounded-lg bg-white/[0.03] border border-white/[0.07] p-4 text-center">
              <div className="text-2xl font-bold text-indigo-400">{result.n_features ?? "—"}</div>
              <div className="text-xs text-white/50 mt-1">Features Used</div>
            </div>
            <div className="rounded-lg bg-white/[0.03] border border-white/[0.07] p-4 text-center">
              <div className="text-xl font-bold text-indigo-400 capitalize">{result.problem_type ?? "—"}</div>
              <div className="text-xs text-white/50 mt-1">Problem Type</div>
            </div>
          </div>

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

          {result.feature_importance?.length > 0 && (
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5">
              <h3 className="text-sm font-semibold text-white/70 uppercase tracking-wider mb-4">Feature Importance — {result.best_model}</h3>
              <ResponsiveContainer width="100%" height={Math.min(result.feature_importance.length * 32 + 20, 380)}>
                <BarChart data={result.feature_importance.slice(0, 15)} layout="vertical" margin={{ left: 10, right: 20 }}>
                  <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                  <YAxis dataKey="feature" type="category" tick={{ fill: "#94a3b8", fontSize: 11 }} width={130} />
                  <Tooltip {...DARK_TOOLTIP} formatter={(v: any) => [v.toFixed(4), "Importance"]} />
                  <Bar dataKey="importance" radius={4}>
                    {result.feature_importance.slice(0, 15).map((_: any, i: number) => (
                      <Cell key={i} fill="#6366f1" fillOpacity={1 - i * 0.04} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {result.preprocessing_notes?.length > 0 && (
            <div className="rounded-lg bg-white/[0.03] border border-white/[0.07] p-4">
              <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">Preprocessing Notes</h3>
              <ul className="text-sm text-white/60 space-y-1">
                {result.preprocessing_notes.map((note: string, i: number) => (
                  <li key={i}>· {note}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Score New Data */}
      {modelInfo && (
        <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-5 space-y-4">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-white">
              Score New Data
              <span className="ml-2 text-xs text-white/40 font-normal">
                using {modelInfo.best_model_name} · predicts {modelInfo.target_col}
              </span>
            </h3>
          </div>

          <p className="text-xs text-white/50">
            Paste a JSON array of row objects. Feature columns:{" "}
            <span className="text-white/70">{modelInfo.feature_names.join(", ")}</span>
          </p>

          <textarea
            className="w-full rounded-lg bg-[#0c0c14] border border-white/[0.08] p-3 font-mono text-xs text-white/80 placeholder-white/20 focus:outline-none focus:border-indigo-500/50 resize-y"
            rows={6}
            value={predictJson}
            onChange={(e) => setPredictJson(e.target.value)}
            spellCheck={false}
          />

          {predictError && (
            <p className="text-xs text-red-400">{predictError}</p>
          )}

          <Button
            onClick={handlePredict}
            disabled={predictLoading}
            className="bg-indigo-600 hover:bg-indigo-500 text-white gap-2"
          >
            {predictLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
            Run Prediction
          </Button>

          {predictResult && (
            <div className="overflow-x-auto rounded-lg border border-white/[0.07]">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-white/[0.07] bg-white/[0.02]">
                    <th className="text-left p-3 text-white/50 font-medium">#</th>
                    <th className="text-left p-3 text-white/50 font-medium">
                      Predicted {predictResult.target_col}
                    </th>
                    {predictResult.predictions[0]?.confidence != null && (
                      <th className="text-left p-3 text-white/50 font-medium">Confidence</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {predictResult.predictions.map((p: any, i: number) => (
                    <tr key={i} className="border-b border-white/[0.04]">
                      <td className="p-3 text-white/30">{i + 1}</td>
                      <td className="p-3 text-indigo-300 font-medium">{String(p.prediction)}</td>
                      {p.confidence != null && (
                        <td className="p-3 text-white/60">
                          {(p.confidence * 100).toFixed(1)}%
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

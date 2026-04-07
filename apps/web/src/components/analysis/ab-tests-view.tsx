/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useState, useEffect } from "react";
import { getStatsColumns, runStatsTest, runPowerAnalysis } from "@/lib/api";
import { ColumnSelect } from "@/components/ui/column-select";
import { Loader2, FlaskConical, CheckCircle, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = { projectId: number };

const TEST_TYPES = [
  { id: "ttest", label: "Welch's T-Test", desc: "Compare means of 2 groups (numeric col + grouping col)" },
  { id: "mannwhitney", label: "Mann-Whitney U", desc: "Non-parametric comparison of 2 groups" },
  { id: "anova", label: "One-way ANOVA", desc: "Compare means across 3+ groups" },
  { id: "kruskal", label: "Kruskal-Wallis", desc: "Non-parametric 3+ group comparison" },
  { id: "chi_square", label: "Chi-Square", desc: "Test independence of 2 categorical variables" },
  { id: "paired_ttest", label: "Paired T-Test", desc: "Compare two related numeric columns" },
  { id: "shapiro", label: "Shapiro-Wilk", desc: "Test if a column is normally distributed" },
];

export function AbTestsView({ projectId }: Props) {
  const [numCols, setNumCols] = useState<string[]>([]);
  const [catCols, setCatCols] = useState<string[]>([]);

  const [testType, setTestType] = useState("ttest");
  const [colA, setColA] = useState("");
  const [colB, setColB] = useState("");
  const [alpha, setAlpha] = useState(0.05);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [effectSize, setEffectSize] = useState(0.5);
  const [power, setPower] = useState(0.8);
  const [powerResult, setPowerResult] = useState<any>(null);
  const [powerLoading, setPowerLoading] = useState(false);

  useEffect(() => {
    getStatsColumns(projectId)
      .then((data: any) => {
        const num: string[] = data.numeric_columns || [];
        const cat: string[] = data.categorical_columns || [];
        setNumCols(num);
        setCatCols(cat);
        if (num.length > 0) setColA(num[0]);
        if (cat.length > 0) setColB(cat[0]);
      })
      .catch(() => setError("Failed to load columns."));
  }, [projectId]);

  async function handleTest() {
    if (!colA) { setError("Select at least Column A."); return; }
    setLoading(true); setError("");
    try {
      const data = await runStatsTest(projectId, testType, colA, colB || undefined, alpha);
      setResult(data);
    } catch (e: any) {
      try { const p = JSON.parse(e.message); setError(p.detail || e.message); }
      catch { setError(e.message || "Test failed."); }
    } finally { setLoading(false); }
  }

  async function handlePower() {
    setPowerLoading(true);
    try {
      const data = await runPowerAnalysis(effectSize, alpha, power, testType);
      setPowerResult(data);
    } catch (e: any) {
      setError(e.message || "Power analysis failed.");
    } finally { setPowerLoading(false); }
  }

  const allCols = [...numCols, ...catCols];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1 flex items-center gap-2">
          <FlaskConical className="h-5 w-5 text-indigo-400" /> Statistical Tests
        </h2>
        <p className="text-sm text-white/50">Run hypothesis tests and compute required sample sizes.</p>
      </div>

      {error && <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</div>}

      <div>
        <label className="block text-xs text-white/50 mb-2 uppercase tracking-wider">Test Type</label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {TEST_TYPES.map((t) => (
            <button key={t.id} onClick={() => setTestType(t.id)}
              className={`text-left rounded-lg border px-3 py-2.5 transition-colors ${testType === t.id ? "border-indigo-500 bg-indigo-500/10" : "border-white/10 bg-white/[0.02] hover:border-white/20"}`}>
              <div className="text-sm font-medium text-white">{t.label}</div>
              <div className="text-xs text-white/40 mt-0.5">{t.desc}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <ColumnSelect
          label="Column A (primary / numeric)"
          value={colA}
          options={allCols}
          onChange={setColA}
        />
        {testType !== "shapiro" && (
          <ColumnSelect
            label="Column B (grouping / secondary)"
            value={colB}
            options={["", ...allCols]}
            optionLabels={{ "": "None" }}
            onChange={setColB}
          />
        )}
        <ColumnSelect
          label="Significance Level (α)"
          value={String(alpha)}
          options={["0.01", "0.05", "0.1"]}
          optionLabels={{ "0.01": "0.01 (strict)", "0.05": "0.05 (standard)", "0.1": "0.10 (lenient)" }}
          onChange={(v) => setAlpha(Number(v))}
        />
      </div>

      <Button onClick={handleTest} disabled={loading} className="bg-indigo-600 hover:bg-indigo-500 text-white gap-2">
        {loading ? <><Loader2 className="h-4 w-4 animate-spin" />Running…</> : "Run Test"}
      </Button>

      {result && (
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5 space-y-4">
          <div className="flex items-center gap-3">
            {result.is_significant
              ? <CheckCircle className="h-6 w-6 text-green-400 flex-shrink-0" />
              : <XCircle className="h-6 w-6 text-red-400 flex-shrink-0" />}
            <div>
              <div className={`text-lg font-semibold ${result.is_significant ? "text-green-400" : "text-red-400"}`}>
                {result.is_significant ? "Statistically Significant" : "Not Significant"}
              </div>
              <div className="text-xs text-white/50">α = {result.alpha}</div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-white/[0.04] p-3 text-center">
              <div className="text-xl font-bold text-white">{result.statistic?.toFixed(4) ?? "—"}</div>
              <div className="text-xs text-white/50">Test Statistic</div>
            </div>
            <div className="rounded-lg bg-white/[0.04] p-3 text-center">
              <div className="text-xl font-bold text-white">{result.p_value?.toFixed(6) ?? "—"}</div>
              <div className="text-xs text-white/50">p-value</div>
            </div>
            <div className="rounded-lg bg-white/[0.04] p-3 text-center">
              <div className="text-xl font-bold text-indigo-400">{result.effect_size?.toFixed(3) ?? "—"}</div>
              <div className="text-xs text-white/50">{result.effect_size_label ?? "Effect Size"} ({result.effect_interpretation ?? ""})</div>
            </div>
          </div>

          <div className="rounded-lg bg-white/[0.04] p-4 text-sm text-white/70 leading-relaxed">
            {result.conclusion}
          </div>

          {result.group_stats?.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-white/[0.07]">
                    <th className="text-left py-2 pr-4 text-white/50 font-medium">Group</th>
                    <th className="text-right py-2 pr-4 text-white/50 font-medium">N</th>
                    {result.group_stats[0]?.mean != null && <th className="text-right py-2 pr-4 text-white/50 font-medium">Mean</th>}
                    {result.group_stats[0]?.std != null && <th className="text-right py-2 text-white/50 font-medium">Std Dev</th>}
                    {result.group_stats[0]?.median != null && <th className="text-right py-2 text-white/50 font-medium">Median</th>}
                  </tr>
                </thead>
                <tbody>
                  {result.group_stats.map((gs: any, i: number) => (
                    <tr key={i} className="border-b border-white/[0.04]">
                      <td className="py-2 pr-4 text-white/70 font-medium">{gs.group}</td>
                      <td className="text-right py-2 pr-4 text-white/70">{gs.n}</td>
                      {gs.mean != null && <td className="text-right py-2 pr-4 text-white/70">{gs.mean?.toFixed(4)}</td>}
                      {gs.std != null && <td className="text-right py-2 text-white/70">{gs.std?.toFixed(4)}</td>}
                      {gs.median != null && <td className="text-right py-2 text-white/70">{gs.median?.toFixed(4)}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5">
        <h3 className="text-sm font-semibold text-white mb-4">Sample Size Calculator</h3>
        <p className="text-xs text-white/40 mb-4">How many samples per group do you need to detect a given effect?</p>
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div>
            <label className="block text-xs text-white/50 mb-1">Effect Size (Cohen&apos;s d)</label>
            <input type="number" value={effectSize} step={0.1} min={0.1} max={2}
              onChange={(e) => setEffectSize(Number(e.target.value))}
              className="w-full rounded-lg bg-white/[0.05] border border-white/10 px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500" />
            <div className="text-xs text-white/30 mt-1">small=0.2, medium=0.5, large=0.8</div>
          </div>
          <div>
            <ColumnSelect
              label="Desired Power (1-β)"
              value={String(power)}
              options={["0.7", "0.8", "0.9", "0.95"]}
              optionLabels={{ "0.7": "0.70", "0.8": "0.80 (standard)", "0.9": "0.90", "0.95": "0.95" }}
              onChange={(v) => setPower(Number(v))}
            />
          </div>
          <div className="flex items-end">
            <Button onClick={handlePower} disabled={powerLoading} className="w-full bg-white/[0.08] hover:bg-white/[0.12] text-white text-sm">
              {powerLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Calculate"}
            </Button>
          </div>
        </div>
        {powerResult && (
          <div className="rounded-lg bg-indigo-500/10 border border-indigo-500/20 p-4 text-center">
            <div className="text-3xl font-bold text-indigo-400">{powerResult.required_n_per_group}</div>
            <div className="text-sm text-white/60 mt-1">required samples per group</div>
            <div className="text-xs text-white/40 mt-2">
              to detect effect size {powerResult.effect_size} with {Math.round((powerResult.power || 0) * 100)}% power at α={powerResult.alpha}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

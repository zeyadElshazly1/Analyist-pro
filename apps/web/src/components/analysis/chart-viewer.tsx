/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable react-hooks/exhaustive-deps */
"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { getSuggestedCharts } from "@/lib/api";
import { TrendingUp, Download } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  LineChart,
  Line,
  ScatterChart,
  Scatter,
  PieChart,
  Pie,
  Cell,
} from "recharts";

type BoxplotEntry = {
  name: string;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  outliers?: number[];
  n?: number;
};

type HeatmapEntry = {
  x: string;
  y: string;
  value: number;
};

type ChartDef = {
  type: "bar" | "line" | "pie" | "scatter" | "boxplot" | "heatmap";
  title: string;
  description?: string;
  insight?: string;
  x_key: string;
  y_key: string;
  x_label?: string;
  y_label?: string;
  data: Array<Record<string, unknown>>;
  regression?: Array<{ x: number; y_hat: number }>;
  columns?: string[];
  recommended?: boolean;
};

type Props = {
  projectId: number;
  autoLoad?: boolean;
};

const DARK_TOOLTIP = {
  contentStyle: {
    background: "#111118",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 8,
    color: "#fff",
    fontSize: 12,
  },
};

const PIE_COLORS = ["#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd", "#818cf8", "#4f46e5", "#7c3aed", "#6d28d9"];
const BG_COLOR = "#0c0c14";

function slugify(title: string) {
  return title.replace(/[^a-z0-9]+/gi, "_").toLowerCase().replace(/^_+|_+$/g, "");
}

function exportChart(containerEl: HTMLDivElement, chart: ChartDef, format: "svg" | "png") {
  const svgEl = containerEl.querySelector("svg");
  if (!svgEl) return;

  const width = svgEl.clientWidth || 600;
  const height = svgEl.clientHeight || 300;

  // Clone and patch background + explicit dimensions
  const clone = svgEl.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("width", String(width));
  clone.setAttribute("height", String(height));
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");

  const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  bg.setAttribute("width", "100%");
  bg.setAttribute("height", "100%");
  bg.setAttribute("fill", BG_COLOR);
  clone.insertBefore(bg, clone.firstChild);

  const svgStr = new XMLSerializer().serializeToString(clone);
  const blob = new Blob([svgStr], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const filename = slugify(chart.title);

  if (format === "svg") {
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}.svg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    return;
  }

  // PNG: render SVG into canvas at 2× for retina
  const scale = 2;
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = width * scale;
    canvas.height = height * scale;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(scale, scale);
    ctx.fillStyle = BG_COLOR;
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(img, 0, 0, width, height);
    URL.revokeObjectURL(url);
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = `${filename}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };
  img.onerror = () => URL.revokeObjectURL(url);
  img.src = url;
}

function BoxplotChart({ chart }: { chart: ChartDef }) {
  const entries = chart.data as unknown as BoxplotEntry[];
  if (!entries || entries.length === 0) {
    return <p className="text-sm text-white/40">No boxplot data available.</p>;
  }

  // Find global min/max for scaling
  const allVals = entries.flatMap((e) => [e.min, e.max]);
  const gMin = Math.min(...allVals);
  const gMax = Math.max(...allVals);
  const range = gMax - gMin || 1;

  const pct = (v: number) => `${Math.max(0, Math.min(100, ((v - gMin) / range) * 100)).toFixed(2)}%`;
  const pctW = (a: number, b: number) => `${Math.max(0, ((b - a) / range) * 100).toFixed(2)}%`;

  return (
    <div className="space-y-3 mt-2">
      {entries.map((entry, i) => (
        <div key={i} className="flex items-center gap-3">
          <span className="w-24 flex-shrink-0 text-right text-xs text-white/50 truncate" title={entry.name}>
            {entry.name}
          </span>
          <div className="relative flex-1 h-6">
            {/* whisker left */}
            <div className="absolute top-1/2 -translate-y-px h-px bg-white/25"
              style={{ left: pct(entry.min), width: pctW(entry.min, entry.q1) }} />
            {/* IQR box */}
            <div className="absolute top-1 h-4 rounded bg-indigo-500/40 border border-indigo-500/60"
              style={{ left: pct(entry.q1), width: pctW(entry.q1, entry.q3) }} />
            {/* median line */}
            <div className="absolute top-1 h-4 w-0.5 bg-indigo-200"
              style={{ left: pct(entry.median) }} />
            {/* whisker right */}
            <div className="absolute top-1/2 -translate-y-px h-px bg-white/25"
              style={{ left: pct(entry.q3), width: pctW(entry.q3, entry.max) }} />
            {/* outlier dots */}
            {(entry.outliers ?? []).slice(0, 10).map((v, oi) => (
              <div key={oi} className="absolute top-1.5 h-3 w-0.5 rounded-full bg-red-400/70"
                style={{ left: pct(v) }} />
            ))}
          </div>
          {entry.n !== undefined && (
            <span className="w-10 flex-shrink-0 text-right text-[10px] text-white/30">n={entry.n}</span>
          )}
        </div>
      ))}
      <div className="flex justify-between text-[10px] text-white/25 px-28">
        <span>{gMin.toFixed(2)}</span>
        <span>{((gMin + gMax) / 2).toFixed(2)}</span>
        <span>{gMax.toFixed(2)}</span>
      </div>
    </div>
  );
}

function HeatmapChart({ chart }: { chart: ChartDef }) {
  const entries = chart.data as unknown as HeatmapEntry[];
  const cols = chart.columns ?? [];

  if (!entries || entries.length === 0 || cols.length === 0) {
    return <p className="text-sm text-white/40">No heatmap data available.</p>;
  }

  // Build lookup
  const lookup: Record<string, number> = {};
  for (const e of entries) lookup[`${e.x}__${e.y}`] = e.value;

  function cellColor(v: number): string {
    if (v >= 0.7) return "bg-indigo-500 text-white";
    if (v >= 0.4) return "bg-indigo-500/50 text-white/90";
    if (v >= 0.2) return "bg-indigo-500/25 text-white/70";
    if (v <= -0.7) return "bg-rose-500 text-white";
    if (v <= -0.4) return "bg-rose-500/50 text-white/90";
    if (v <= -0.2) return "bg-rose-500/25 text-white/70";
    return "bg-white/[0.04] text-white/40";
  }

  const cellSize = cols.length > 5 ? "text-[9px]" : "text-xs";

  return (
    <div className="overflow-x-auto mt-2">
      <table className="w-full border-collapse text-center" style={{ minWidth: cols.length * 52 }}>
        <thead>
          <tr>
            <th className="w-10" />
            {cols.map((c) => (
              <th key={c} className={`pb-1 font-normal text-white/40 ${cellSize} max-w-[52px] truncate px-0.5`} title={c}>
                {c.length > 8 ? c.slice(0, 7) + "…" : c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cols.map((rowCol) => (
            <tr key={rowCol}>
              <td className={`text-right pr-1 font-normal text-white/40 ${cellSize} max-w-[40px] truncate`} title={rowCol}>
                {rowCol.length > 8 ? rowCol.slice(0, 7) + "…" : rowCol}
              </td>
              {cols.map((colCol) => {
                const v = lookup[`${rowCol}__${colCol}`] ?? 0;
                const isdiag = rowCol === colCol;
                return (
                  <td key={colCol}
                    className={`p-0.5`}
                    title={`${rowCol} vs ${colCol}: ${v.toFixed(3)}`}>
                    <div className={`rounded text-center py-1 ${cellSize} font-medium ${isdiag ? "bg-white/[0.08] text-white/50" : cellColor(v)}`}
                      style={{ minWidth: 40 }}>
                      {isdiag ? "—" : v.toFixed(2)}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SingleChart({ chart }: { chart: ChartDef }) {
  if (!chart.data || chart.data.length === 0) {
    return <p className="text-sm text-white/40">No data available for this chart.</p>;
  }

  if (chart.type === "boxplot") {
    return <BoxplotChart chart={chart} />;
  }

  if (chart.type === "heatmap") {
    return <HeatmapChart chart={chart} />;
  }

  if (chart.type === "line") {
    return (
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chart.data}>
            <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.1} />
            <XAxis dataKey={chart.x_key} tick={{ fill: "#6b7280", fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
            <Tooltip {...DARK_TOOLTIP} />
            <Line type="monotone" dataKey={chart.y_key} stroke="#6366f1" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chart.type === "scatter") {
    return (
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.1} />
            <XAxis
              dataKey="x"
              name={chart.x_label ?? chart.x_key}
              tick={{ fill: "#6b7280", fontSize: 11 }}
              label={{ value: chart.x_label, position: "insideBottom", offset: -5, fill: "#9ca3af", fontSize: 11 }}
            />
            <YAxis
              dataKey="y"
              name={chart.y_label ?? chart.y_key}
              tick={{ fill: "#6b7280", fontSize: 11 }}
              label={{ value: chart.y_label, angle: -90, position: "insideLeft", fill: "#9ca3af", fontSize: 11 }}
            />
            <Tooltip {...DARK_TOOLTIP} cursor={{ strokeDasharray: "3 3" }} />
            <Scatter data={chart.data} fill="#6366f1" fillOpacity={0.5} r={3} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chart.type === "pie") {
    return (
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chart.data}
              dataKey={chart.y_key}
              nameKey={chart.x_key}
              cx="50%"
              cy="50%"
              outerRadius={90}
              label={({ name, percent }: any) => `${name}: ${(percent * 100).toFixed(0)}%`}
              labelLine={{ stroke: "rgba(255,255,255,0.2)" }}
            >
              {chart.data.map((_: unknown, index: number) => (
                <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip {...DARK_TOOLTIP} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Default: bar
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chart.data}>
          <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.1} />
          <XAxis
            dataKey={chart.x_key}
            tick={{ fill: "#6b7280", fontSize: 11 }}
            angle={-15}
            textAnchor="end"
            height={50}
            interval={0}
          />
          <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
          <Tooltip {...DARK_TOOLTIP} />
          <Bar dataKey={chart.y_key} fill="#6366f1" fillOpacity={0.8} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function DownloadMenu({
  onExport,
}: {
  onExport: (fmt: "svg" | "png") => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        title="Download chart"
        className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-white/40 hover:bg-white/[0.06] hover:text-white/70 transition-colors"
      >
        <Download className="h-3.5 w-3.5" />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-20 mt-1 w-28 rounded-lg border border-white/[0.08] bg-[#111118] shadow-xl overflow-hidden">
          {(["PNG", "SVG"] as const).map((fmt) => (
            <button
              key={fmt}
              onClick={() => {
                setOpen(false);
                onExport(fmt.toLowerCase() as "svg" | "png");
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-xs text-white/60 hover:bg-white/[0.06] hover:text-white transition-colors"
            >
              <Download className="h-3 w-3" />
              {fmt === "PNG" ? "Download PNG" : "Download SVG"}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function ChartViewer({ projectId, autoLoad }: Props) {
  const [loading, setLoading] = useState(false);
  const [charts, setCharts] = useState<ChartDef[]>([]);
  const [error, setError] = useState("");
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);

  const loadCharts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getSuggestedCharts(projectId);
      setCharts((res.charts ?? []) as ChartDef[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load charts.");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (autoLoad) loadCharts();
  }, [projectId, autoLoad, loadCharts]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {[0, 1, 2, 4].map((i) => (
          <div key={i} className="h-80 rounded-xl bg-white/[0.04] animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-red-400">{error}</p>
        <button
          onClick={loadCharts}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500"
        >
          Retry
        </button>
      </div>
    );
  }

  if (charts.length === 0) {
    return (
      <div className="space-y-3">
        <button
          onClick={loadCharts}
          disabled={loading}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          Generate Charts
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-white/40">{charts.length} charts generated</p>
        <button
          onClick={loadCharts}
          className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
        >
          Regenerate
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {charts.map((chart, i) => (
          <div
            key={i}
            ref={(el) => { cardRefs.current[i] = el; }}
            className={`rounded-xl border bg-white/[0.03] p-4 space-y-2 ${chart.recommended ? "border-indigo-500/30" : "border-white/[0.07]"}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  {chart.recommended && (
                    <TrendingUp className="h-3.5 w-3.5 text-indigo-400 flex-shrink-0" />
                  )}
                  <h3 className="text-sm font-semibold text-white truncate">{chart.title}</h3>
                </div>
                {chart.insight && (
                  <p className="mt-0.5 text-xs text-white/40 line-clamp-2">{chart.insight}</p>
                )}
              </div>
              <div className="flex flex-shrink-0 items-center gap-1">
                <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-xs text-white/40">
                  {chart.type}
                </span>
                <DownloadMenu
                  onExport={(fmt) => {
                    if (cardRefs.current[i]) {
                      exportChart(cardRefs.current[i]!, chart, fmt);
                    }
                  }}
                />
              </div>
            </div>
            <SingleChart chart={chart} />
          </div>
        ))}
      </div>
    </div>
  );
}

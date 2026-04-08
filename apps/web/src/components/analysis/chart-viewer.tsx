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

type ChartDef = {
  type: "bar" | "line" | "pie" | "scatter";
  title: string;
  description?: string;
  insight?: string;
  x_key: string;
  y_key: string;
  x_label?: string;
  y_label?: string;
  data: Array<Record<string, unknown>>;
  regression?: Array<{ x: number; y_hat: number }>;
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

function SingleChart({ chart }: { chart: ChartDef }) {
  if (!chart.data || chart.data.length === 0) {
    return <p className="text-sm text-white/40">No data available for this chart.</p>;
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

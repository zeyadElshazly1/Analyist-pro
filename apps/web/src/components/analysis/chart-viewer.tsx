/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useState, useEffect, useRef, useCallback, useMemo, type RefObject } from "react";
import { getSuggestedCharts } from "@/lib/api";
import { Download, X, Info, ChevronRight } from "lucide-react";
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
  /** Server hint: render as horizontal bars (category on Y). */
  horizontal?: boolean;
  /** Numeric 0/1 flag column — prefer short, unrotated category labels. */
  is_binary?: boolean;
};

/** Backend time-series payloads use x_key `date` and ISO-ish strings in data rows. */
function sampleCellLooksLikeDate(value: unknown): boolean {
  if (value == null) return false;
  const s = String(value).trim();
  if (s.length < 8) return false;
  const t = Date.parse(s);
  return !Number.isNaN(t);
}

function lineChartHasPlausibleTimeAxis(chart: ChartDef): boolean {
  if (chart.type !== "line") return true;
  const xk = chart.x_key ?? "";
  if (xk.toLowerCase() !== "date") return false;
  const rows = chart.data ?? [];
  if (rows.length < 2) return false;
  const sample = rows.slice(0, Math.min(16, rows.length));
  const parsed = sample.filter((r) => sampleCellLooksLikeDate(r[xk])).length;
  return parsed >= Math.max(2, Math.ceil(sample.length * 0.35));
}

function chartDisplaySignature(chart: ChartDef): string {
  return `${chart.type}|${(chart.title ?? "").trim().toLowerCase()}|${chart.x_key}|${chart.y_key}`;
}

function sanitizeLineChartInsight(chart: ChartDef): ChartDef {
  if (chart.type !== "line" || !chart.insight) return chart;
  let insight = chart.insight;
  if (/\d{6,}%/.test(insight)) {
    return {
      ...chart,
      insight:
        "Trend is shown in the chart; endpoint percentage summaries are omitted when they are not reliable.",
    };
  }
  insight = insight.replace(
    /\b(increased|decreased)\s+by\s+1[,0-9]{3,}\.?\d*%/gi,
    "changed sharply (see chart)",
  );
  return { ...chart, insight };
}

function filterChartsForDisplay(charts: ChartDef[]): ChartDef[] {
  const seen = new Set<string>();
  const out: ChartDef[] = [];
  for (const raw of charts) {
    if (raw.type === "line" && !lineChartHasPlausibleTimeAxis(raw)) continue;
    const sig = chartDisplaySignature(raw);
    if (seen.has(sig)) continue;
    seen.add(sig);
    out.push(sanitizeLineChartInsight(raw));
  }
  return out;
}

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

/** Recharts Tooltip formatter: `value` may be undefined per library typings. */
function barCountTooltipFormatter(yLabel: string | undefined) {
  return (value: unknown) => [String(value ?? "—"), yLabel ?? "Count"] as const;
}

const PIE_COLORS = ["#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd", "#818cf8", "#4f46e5", "#7c3aed", "#6d28d9"];
const BG_COLOR = "#0c0c14";

/** Full-height plot for legacy / non-preview contexts. */
const CHART_PLOT_HEIGHT = 440;
/** Compact plot inside grid cards (preview). */
const CHART_PREVIEW_PLOT_HEIGHT = 220;
/** Minimum card height so the grid aligns cleanly. */
const CHART_CARD_MIN_HEIGHT = 336;
/** Taller plot in Chart Detail modal / drawer. */
const DETAIL_CHART_PLOT_HEIGHT = 520;
const MAX_CATEGORY_TICKS = 9;
const PREVIEW_CATEGORY_TICKS = 4;
const DETAIL_TABLE_MAX_ROWS = 120;

function longestCategoryLabel(rows: Array<Record<string, unknown>>, key: string): number {
  let m = 0;
  for (const row of rows) {
    const v = row[key];
    if (v != null) m = Math.max(m, String(v).length);
  }
  return m;
}

function chartTickInterval(barCount: number, maxTicks: number): number | "preserveStartEnd" {
  if (barCount <= maxTicks) return "preserveStartEnd";
  return Math.max(0, Math.ceil(barCount / maxTicks) - 1);
}

function TruncatedRotatedTick({
  x = 0,
  y = 0,
  payload,
  rotate,
  maxChars,
}: {
  x?: number | string;
  y?: number | string;
  payload?: { value?: unknown };
  rotate: number;
  maxChars: number;
}) {
  const raw = String(payload?.value ?? "");
  const show = raw.length > maxChars ? `${raw.slice(0, maxChars - 1)}…` : raw;
  const tx = Number(x);
  const ty = Number(y);
  return (
    <g transform={`translate(${Number.isFinite(tx) ? tx : 0},${Number.isFinite(ty) ? ty : 0})`}>
      <title>{raw}</title>
      <text
        fill="#9ca3af"
        fontSize={11}
        textAnchor={rotate ? "end" : "middle"}
        transform={rotate ? `rotate(${rotate},0,0)` : undefined}
        dy={rotate ? 12 : 14}
      >
        {show}
      </text>
    </g>
  );
}

function HorizontalBarPanel({
  chart,
  plotHeight = CHART_PLOT_HEIGHT,
  variant = "detail",
}: {
  chart: ChartDef;
  plotHeight?: number;
  variant?: "preview" | "detail";
}) {
  const isPreview = variant === "preview";
  const rows = chart.data;
  const n = rows.length;
  const labelChars = longestCategoryLabel(rows, chart.x_key);
  const yAxisWidth = isPreview
    ? Math.min(112, 40 + Math.min(labelChars, 10) * 6)
    : Math.min(220, 48 + Math.min(labelChars, 36) * 7);
  const yTickInterval = isPreview ? chartTickInterval(n, PREVIEW_CATEGORY_TICKS) : 0;
  const tickTruncate = isPreview ? 14 : 32;

  return (
    <div
      className="w-full min-w-0"
      style={{ height: plotHeight, minHeight: plotHeight }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ left: 8, right: isPreview ? 8 : 16, top: 8, bottom: 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.12} horizontal />
          <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: isPreview ? 9 : 11 }} tickCount={isPreview ? 4 : 6} />
          <YAxis
            type="category"
            dataKey={chart.x_key}
            width={yAxisWidth}
            tick={{ fill: "#9ca3af", fontSize: isPreview ? 9 : 11 }}
            tickFormatter={(v: string) => {
              const s = String(v);
              return s.length > tickTruncate ? `${s.slice(0, tickTruncate - 1)}…` : s;
            }}
            interval={yTickInterval}
          />
          <Tooltip
            {...DARK_TOOLTIP}
            formatter={barCountTooltipFormatter(chart.y_label)}
            labelFormatter={(label) => String(label)}
          />
          <Bar
            dataKey={chart.y_key}
            fill="#6366f1"
            fillOpacity={0.88}
            radius={[0, 5, 5, 0]}
            maxBarSize={38}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function VerticalBarPanel({
  chart,
  plotHeight = CHART_PLOT_HEIGHT,
  variant = "detail",
}: {
  chart: ChartDef;
  plotHeight?: number;
  variant?: "preview" | "detail";
}) {
  const isPreview = variant === "preview";
  const rows = chart.data;
  const n = rows.length;
  const isBinary = chart.is_binary === true;
  const maxLabLen = longestCategoryLabel(rows, chart.x_key);
  const maxCatTicks = isPreview ? PREVIEW_CATEGORY_TICKS : MAX_CATEGORY_TICKS;
  const needsRotate = !isPreview && !isBinary && (n > 6 || maxLabLen > 11);
  const rotate = isBinary ? 0 : needsRotate ? -38 : 0;
  const bottomGutter = isPreview
    ? (isBinary ? 24 : Math.min(40, 24 + Math.min(maxLabLen, 8)))
    : isBinary
      ? 32
      : rotate
        ? Math.min(108, 40 + Math.min(maxLabLen, 20) * 2.2)
        : 52;
  const tickMaxChars = isPreview ? 8 : rotate ? 16 : 22;
  const interval = isBinary ? 0 : chartTickInterval(n, maxCatTicks);

  return (
    <div
      className="w-full min-w-0"
      style={{ height: plotHeight, minHeight: plotHeight }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ left: 4, right: isPreview ? 8 : 12, top: isPreview ? 6 : 12, bottom: bottomGutter }}>
          <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.12} />
          <XAxis
            dataKey={chart.x_key}
            interval={interval}
            tick={(props) => (
              <TruncatedRotatedTick
                x={props.x}
                y={props.y}
                payload={props.payload}
                rotate={rotate}
                maxChars={tickMaxChars}
              />
            )}
            height={bottomGutter + 8}
            axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
            tickLine={{ stroke: "rgba(255,255,255,0.06)" }}
          />
          <YAxis
            tick={{ fill: "#9ca3af", fontSize: isPreview ? 9 : 11 }}
            axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
            tickLine={{ stroke: "rgba(255,255,255,0.06)" }}
          />
          <Tooltip
            {...DARK_TOOLTIP}
            formatter={barCountTooltipFormatter(chart.y_label)}
            labelFormatter={(label) => String(label)}
          />
          <Bar
            dataKey={chart.y_key}
            fill="#6366f1"
            fillOpacity={0.88}
            radius={[5, 5, 0, 0]}
            maxBarSize={n > 14 ? 32 : 48}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function BarPanels({
  chart,
  plotHeight = CHART_PLOT_HEIGHT,
  variant = "detail",
}: {
  chart: ChartDef;
  plotHeight?: number;
  variant?: "preview" | "detail";
}) {
  const rows = chart.data;
  const n = rows.length;
  const maxLab = longestCategoryLabel(rows, chart.x_key);
  const useHorizontal =
    chart.horizontal === true || (!chart.is_binary && (n > 12 || maxLab > 18));

  if (useHorizontal) {
    return <HorizontalBarPanel chart={chart} plotHeight={plotHeight} variant={variant} />;
  }
  return <VerticalBarPanel chart={chart} plotHeight={plotHeight} variant={variant} />;
}

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

function BoxplotChart({ chart, variant = "detail" }: { chart: ChartDef; variant?: "preview" | "detail" }) {
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

  const isPreview = variant === "preview";
  const showEntries = isPreview ? entries.slice(0, 6) : entries;

  return (
    <div
      className={`space-y-2 mt-1 ${isPreview ? "max-h-[200px] overflow-y-auto pr-1" : "space-y-3 mt-2"}`}
    >
      {showEntries.map((entry, i) => (
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

function HeatmapChart({ chart, variant = "detail" }: { chart: ChartDef; variant?: "preview" | "detail" }) {
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
  const isPreview = variant === "preview";

  return (
    <div className={`overflow-x-auto mt-1 ${isPreview ? "max-h-[200px]" : "mt-2"}`}>
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

function SingleChart({
  chart,
  plotHeight,
  variant = "detail",
}: {
  chart: ChartDef;
  plotHeight?: number;
  variant?: "preview" | "detail";
}) {
  if (!chart.data || chart.data.length === 0) {
    return <p className="text-sm text-white/40">No data available for this chart.</p>;
  }

  if (chart.type === "boxplot") {
    return <BoxplotChart chart={chart} variant={variant} />;
  }

  if (chart.type === "heatmap") {
    return <HeatmapChart chart={chart} variant={variant} />;
  }

  const isPreview = variant === "preview";
  const h =
    plotHeight ??
    (isPreview ? CHART_PREVIEW_PLOT_HEIGHT : CHART_PLOT_HEIGHT);
  const plotBoxStyle = { height: h, minHeight: h };

  if (chart.type === "line") {
    const n = chart.data.length;
    const angled = !isPreview && n > 10;
    const maxXTicks = isPreview ? PREVIEW_CATEGORY_TICKS : angled ? 8 : 12;
    const bottomMargin = isPreview ? 22 : angled ? 64 : 28;
    return (
      <div className="w-full min-w-0" style={plotBoxStyle}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chart.data}
            margin={{ left: 4, right: 6, top: 6, bottom: bottomMargin }}
          >
            <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.12} />
            <XAxis
              dataKey={chart.x_key}
              tick={{ fill: "#9ca3af", fontSize: isPreview ? 8 : angled ? 9 : 11 }}
              interval={chartTickInterval(n, maxXTicks)}
              minTickGap={isPreview ? 48 : angled ? 20 : 28}
              angle={angled ? -42 : 0}
              textAnchor={angled ? "end" : "middle"}
              height={isPreview ? 28 : angled ? 56 : 32}
            />
            <YAxis tick={{ fill: "#9ca3af", fontSize: isPreview ? 9 : 11 }} />
            <Tooltip {...DARK_TOOLTIP} />
            <Line type="monotone" dataKey={chart.y_key} stroke="#6366f1" strokeWidth={isPreview ? 1.5 : 2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chart.type === "scatter") {
    return (
      <div className="w-full min-w-0" style={plotBoxStyle}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ left: 4, right: 8, top: 8, bottom: isPreview ? 4 : 8 }}>
            <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.12} />
            <XAxis
              dataKey="x"
              name={chart.x_label ?? chart.x_key}
              tick={{ fill: "#9ca3af", fontSize: isPreview ? 9 : 11 }}
              tickCount={isPreview ? 4 : 8}
              label={
                isPreview
                  ? undefined
                  : { value: chart.x_label, position: "insideBottom", offset: -4, fill: "#9ca3af", fontSize: 11 }
              }
            />
            <YAxis
              dataKey="y"
              name={chart.y_label ?? chart.y_key}
              tick={{ fill: "#9ca3af", fontSize: isPreview ? 9 : 11 }}
              tickCount={isPreview ? 4 : 8}
              label={
                isPreview
                  ? undefined
                  : { value: chart.y_label, angle: -90, position: "insideLeft", fill: "#9ca3af", fontSize: 11 }
              }
            />
            <Tooltip {...DARK_TOOLTIP} cursor={{ strokeDasharray: "3 3" }} />
            <Scatter data={chart.data} fill="#6366f1" fillOpacity={0.5} r={isPreview ? 2 : 3} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chart.type === "pie") {
    return (
      <div className="w-full min-w-0" style={plotBoxStyle}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chart.data}
              dataKey={chart.y_key}
              nameKey={chart.x_key}
              cx="50%"
              cy="50%"
              outerRadius={isPreview ? 64 : 118}
              label={
                isPreview
                  ? false
                  : ({ name, percent }: any) => `${name}: ${(percent * 100).toFixed(0)}%`
              }
              labelLine={isPreview ? false : { stroke: "rgba(255,255,255,0.2)" }}
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

  // Default: bar (histogram, categorical, binary)
  return <BarPanels chart={chart} plotHeight={h} variant={variant} />;
}

function chartDetailTableColumns(chart: ChartDef): string[] {
  const rows = chart.data ?? [];
  if (rows.length === 0) return [];
  const keys = new Set<string>();
  for (const row of rows.slice(0, 50)) {
    Object.keys(row).forEach((k) => keys.add(k));
  }
  const ordered = [chart.x_key, chart.y_key].filter((k) => k && keys.has(k));
  const rest = [...keys].filter((k) => !ordered.includes(k)).sort();
  return [...ordered, ...rest];
}

function chartDetailCaveatLines(insight?: string, chartType?: ChartDef["type"]): string[] {
  const lines: string[] = [];
  const low = (insight ?? "").toLowerCase();
  if (
    low.includes("not meaningful") ||
    low.includes("near-zero baseline") ||
    low.includes("numerically unstable") ||
    low.includes("omitted when") ||
    low.includes("endpoint percentage")
  ) {
    lines.push(
      "Automatic narration may downplay or omit endpoint percentages when baselines are tiny or the series is volatile — use the table and chart for exact values.",
    );
  }
  if (chartType === "line") {
    lines.push(
      "This line ties values in calendar order; gaps between dates and seasonality are not modeled automatically.",
    );
  }
  if (chartType === "scatter") {
    lines.push("A pattern in the scatter plot does not prove causation — consider confounders.");
  }
  if (chartType === "pie") {
    lines.push("Small segments can be hard to read; use the data table for exact shares.");
  }
  return lines;
}

function ChartDetailOverlay({
  chart,
  open,
  onClose,
  chartExportRef,
}: {
  chart: ChartDef | null;
  open: boolean;
  onClose: () => void;
  chartExportRef: RefObject<HTMLDivElement | null>;
}) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !chart) return null;

  const tableCols = chartDetailTableColumns(chart);
  const tableRows = (chart.data ?? []).slice(0, DETAIL_TABLE_MAX_ROWS);
  const colList = chart.columns?.length
    ? chart.columns.join(", ")
    : "—";
  const caveats = chartDetailCaveatLines(chart.insight, chart.type);
  const interpretation =
    [chart.insight, chart.description].filter(Boolean).join(" ") ||
    "Explore the chart and metrics below to understand this view of your data.";

  const kpis = [
    { label: "Rows plotted", value: String(chart.data?.length ?? 0) },
    { label: "X field", value: chart.x_label || chart.x_key },
    { label: "Y field", value: chart.y_label || chart.y_key },
    {
      label: chart.type === "heatmap" ? "Matrix columns (n)" : "Extra columns (n)",
      value: chart.columns?.length != null ? String(chart.columns.length) : "—",
    },
  ];

  return (
    <div className="fixed inset-0 z-[100] flex flex-col justify-end sm:justify-center sm:p-4" role="presentation">
      <button
        type="button"
        aria-label="Close chart detail"
        className="absolute inset-0 bg-black/65 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="chart-detail-title"
        className="relative z-10 flex max-h-[min(94vh,920px)] w-full flex-col rounded-t-2xl border border-white/[0.1] bg-[#0e0e16] shadow-2xl sm:mx-auto sm:max-w-5xl sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-shrink-0 items-start justify-between gap-3 border-b border-white/[0.08] px-4 py-3 sm:px-6">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 id="chart-detail-title" className="text-base font-semibold text-white sm:text-lg">
                {chart.title}
              </h2>
              <span className="rounded-full bg-white/[0.08] px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide text-white/45">
                {chart.type}
              </span>
              {chart.recommended ? (
                <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-300">
                  Recommended
                </span>
              ) : null}
            </div>
          </div>
          <div className="flex flex-shrink-0 items-center gap-2">
            <div onClick={(e) => e.stopPropagation()} className="flex items-center">
              <DownloadMenu
                onExport={(fmt) => {
                  const el = chartExportRef.current;
                  if (el) exportChart(el, chart, fmt);
                }}
              />
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-2 text-white/45 transition-colors hover:bg-white/[0.08] hover:text-white"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5 space-y-5">
          {/* Interpretation — mirrors ColumnCompare banner */}
          <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/10 px-4 py-3 text-sm leading-relaxed text-indigo-100/95">
            {interpretation}
          </div>

          {/* KPI cards — mirrors ColumnCompare metric grid */}
          <div>
            <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-white/35">Key metrics</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {kpis.map(({ label, value }) => (
                <div
                  key={label}
                  className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3 text-center"
                >
                  <p className="text-xs text-white/40">{label}</p>
                  <p className="mt-1 break-words text-sm font-semibold text-white">{value}</p>
                </div>
              ))}
            </div>
            <p className="mt-2 text-xs text-white/35">
              <span className="font-medium text-white/45">columns: </span>
              <span className="font-mono text-[11px] text-white/55">{colList}</span>
            </p>
            <p className="mt-1 text-xs text-white/35">
              <span className="font-medium text-white/45">x_key / y_key: </span>
              <span className="font-mono text-[11px] text-white/55">
                {chart.x_key} · {chart.y_key}
              </span>
            </p>
          </div>

          {/* Chart */}
          <div>
            <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-white/35">Chart</p>
            <div
              ref={chartExportRef}
              className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 sm:p-4"
            >
              <SingleChart chart={chart} plotHeight={DETAIL_CHART_PLOT_HEIGHT} variant="detail" />
            </div>
          </div>

          {/* Supporting data */}
          <div>
            <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-white/35">
              Supporting data
              {chart.data && chart.data.length > DETAIL_TABLE_MAX_ROWS ? (
                <span className="ml-2 font-normal normal-case text-white/30">
                  (first {DETAIL_TABLE_MAX_ROWS} of {chart.data.length} rows)
                </span>
              ) : null}
            </p>
            <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
              <table className="w-full min-w-[280px] text-left text-xs">
                <thead>
                  <tr className="border-b border-white/[0.07] bg-white/[0.03]">
                    {tableCols.map((col) => (
                      <th key={col} className="whitespace-nowrap px-3 py-2 font-medium text-white/45">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableRows.map((row, ri) => (
                    <tr key={ri} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                      {tableCols.map((col) => (
                        <td key={col} className="max-w-[14rem] truncate px-3 py-1.5 text-white/65" title={String(row[col] ?? "")}>
                          {row[col] == null ? "—" : String(row[col])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {caveats.length > 0 ? (
            <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3">
              <div className="flex items-start gap-2 text-sm text-amber-100/90">
                <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-400/80" />
                <div className="space-y-2">
                  <p className="font-medium text-amber-200/95">Caveats</p>
                  <ul className="list-disc space-y-1 pl-4 text-xs leading-relaxed text-amber-100/85">
                    {caveats.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>
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
  const [detailChart, setDetailChart] = useState<ChartDef | null>(null);
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);
  const detailExportRef = useRef<HTMLDivElement | null>(null);

  const displayCharts = useMemo(() => filterChartsForDisplay(charts), [charts]);

  useEffect(() => {
    if (!detailChart) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [detailChart]);

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
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        {[0, 1, 2, 4].map((i) => (
          <div key={i} className="h-[340px] rounded-2xl bg-white/[0.04] animate-pulse" />
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

  if (displayCharts.length === 0) {
    return (
      <div className="space-y-3">
        {charts.length > 0 && (
          <p className="text-sm text-amber-400/90">
            The server returned {charts.length} chart{charts.length === 1 ? "" : "s"}, but none are shown after
            removing invalid time-series or duplicate entries. Use Regenerate or adjust the dataset.
          </p>
        )}
        <button
          onClick={loadCharts}
          disabled={loading}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {charts.length > 0 ? "Regenerate" : "Generate Charts"}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <ChartDetailOverlay
        chart={detailChart}
        open={detailChart != null}
        onClose={() => setDetailChart(null)}
        chartExportRef={detailExportRef}
      />

      <div className="flex items-center justify-between">
        <p className="text-sm text-white/40">{displayCharts.length} charts generated</p>
        <button
          onClick={loadCharts}
          className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
        >
          Regenerate
        </button>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        {displayCharts.map((chart, i) => {
          const nBars = chart.type === "bar" ? chart.data.length : 0;
          const prefersWide =
            chart.type === "bar" && (chart.horizontal === true || nBars > 10);
          return (
            <div
              key={`${chartDisplaySignature(chart)}-${i}`}
              role="button"
              tabIndex={0}
              aria-label={`Open chart detail: ${chart.title}`}
              onClick={() => setDetailChart(chart)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setDetailChart(chart);
                }
              }}
              ref={(el) => { cardRefs.current[i] = el; }}
              style={{ minHeight: CHART_CARD_MIN_HEIGHT }}
              className={`group min-w-0 flex flex-col rounded-2xl border bg-gradient-to-b from-white/[0.06] to-white/[0.02] p-4 shadow-lg shadow-black/25 cursor-pointer transition-colors hover:border-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/45 sm:p-5 ${
                prefersWide ? "xl:col-span-2" : ""
              } ${chart.recommended ? "border-indigo-500/35" : "border-white/[0.08]"}`}
            >
              <div className="flex flex-shrink-0 items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-semibold tracking-tight text-white leading-snug">{chart.title}</h3>
                  {chart.insight ? (
                    <p className="mt-1 text-xs leading-snug text-white/45 line-clamp-1">{chart.insight}</p>
                  ) : null}
                  <p className="mt-2 flex items-center gap-0.5 text-[11px] font-medium text-indigo-400/90 opacity-90 transition group-hover:text-indigo-300 group-hover:opacity-100">
                    Open chart
                    <ChevronRight className="h-3.5 w-3.5" aria-hidden />
                  </p>
                </div>
                <div
                  className="flex flex-shrink-0 items-center gap-1.5"
                  onClick={(e) => e.stopPropagation()}
                  onKeyDown={(e) => e.stopPropagation()}
                >
                  <span className="rounded-full bg-white/[0.07] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-white/45">
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
              <div className="mt-3 flex min-h-0 flex-1 flex-col justify-end">
                <div
                  className="w-full flex-shrink-0 overflow-hidden rounded-lg border border-white/[0.05] bg-white/[0.02]"
                  style={{ height: CHART_PREVIEW_PLOT_HEIGHT, minHeight: CHART_PREVIEW_PLOT_HEIGHT }}
                >
                  <SingleChart chart={chart} variant="preview" />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

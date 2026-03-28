"use client";

import { useEffect, useState } from "react";
import { getSuggestedChart } from "@/lib/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  LineChart, Line,
  PieChart, Pie, Cell,
  ScatterChart, Scatter,
} from "recharts";

type ChartResult = {
  chart_type: "bar" | "line" | "pie" | "scatter";
  title: string;
  x_key: string;
  y_key: string;
  data: Array<Record<string, string | number>>;
};

const PALETTE = ["#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd", "#818cf8", "#4f46e5", "#7c3aed"];

const TOOLTIP_STYLE = {
  background: "#111113",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: "8px",
  color: "#f5f7fa",
  fontSize: 12,
};

function SingleChart({ chart }: { chart: ChartResult }) {
  if (!chart.data || chart.data.length === 0) {
    return (
      <div className="flex h-[260px] items-center justify-center">
        <p className="text-sm text-white/30">No data available</p>
      </div>
    );
  }

  const tickStyle = { fill: "#6b7280", fontSize: 11 };
  const gridProps = { strokeDasharray: "3 3", strokeOpacity: 0.08 };

  if (chart.chart_type === "pie") {
    return (
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie
            data={chart.data}
            dataKey={chart.y_key}
            nameKey={chart.x_key}
            cx="50%"
            cy="50%"
            outerRadius={95}
            innerRadius={50}
            paddingAngle={2}
          >
            {chart.data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={TOOLTIP_STYLE} />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  if (chart.chart_type === "line") {
    return (
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={chart.data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey={chart.x_key} tick={tickStyle} />
          <YAxis tick={tickStyle} width={40} />
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          <Line
            type="monotone"
            dataKey={chart.y_key}
            stroke="#6366f1"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: "#6366f1" }}
          />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (chart.chart_type === "scatter") {
    return (
      <ResponsiveContainer width="100%" height={260}>
        <ScatterChart margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey={chart.x_key} name={chart.x_key} tick={tickStyle} />
          <YAxis dataKey={chart.y_key} name={chart.y_key} tick={tickStyle} width={40} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={TOOLTIP_STYLE} />
          <Scatter data={chart.data} fill="#6366f1" fillOpacity={0.7} />
        </ScatterChart>
      </ResponsiveContainer>
    );
  }

  // bar (default)
  const hasLongLabels = chart.data.some((d) => String(d[chart.x_key]).length > 6);
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart
        data={chart.data}
        margin={{ top: 4, right: 4, bottom: hasLongLabels ? 50 : 10, left: 4 }}
      >
        <CartesianGrid {...gridProps} />
        <XAxis
          dataKey={chart.x_key}
          tick={tickStyle}
          angle={hasLongLabels ? -35 : 0}
          textAnchor={hasLongLabels ? "end" : "middle"}
          interval={0}
        />
        <YAxis tick={tickStyle} width={40} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Bar dataKey={chart.y_key} fill="#6366f1" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

type Props = {
  projectId: number;
  autoLoad?: boolean;
};

export function ChartViewer({ projectId, autoLoad = false }: Props) {
  const [loading, setLoading] = useState(false);
  const [charts, setCharts] = useState<ChartResult[] | null>(null);
  const [error, setError] = useState("");

  async function loadCharts() {
    try {
      setLoading(true);
      setError("");
      const data = await getSuggestedChart(projectId);
      setCharts(Array.isArray(data) ? data : [data]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load charts.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (autoLoad) loadCharts();
  }, [autoLoad, projectId]);

  if (loading) {
    return (
      <div className="flex items-center gap-3 py-8 text-sm text-white/40">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/15 border-t-indigo-500" />
        Generating charts…
      </div>
    );
  }

  if (!charts && !autoLoad) {
    return (
      <button
        onClick={loadCharts}
        className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
      >
        Generate charts
      </button>
    );
  }

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-red-400">{error}</p>}
      {charts && (
        <div className="grid gap-4 md:grid-cols-2">
          {charts.map((chart, i) => (
            <div key={i} className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
              <p className="mb-4 text-sm font-medium text-white/80">{chart.title}</p>
              <SingleChart chart={chart} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

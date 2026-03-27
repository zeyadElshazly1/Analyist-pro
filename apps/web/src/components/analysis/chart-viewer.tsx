"use client";

import { useState } from "react";
import { getSuggestedChart } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

type Props = {
  projectId: number;
};

type ChartResult = {
  chart_type: string;
  title: string;
  x_key: string;
  y_key: string;
  data: Array<Record<string, string | number>>;
};

export function ChartViewer({ projectId }: Props) {
  const [loading, setLoading] = useState(false);
  const [chart, setChart] = useState<ChartResult | null>(null);
  const [message, setMessage] = useState("");

  async function handleLoadChart() {
    try {
      setLoading(true);
      setMessage("");
      const data = await getSuggestedChart(projectId);
      setChart(data);
    } catch (error) {
      if (error instanceof Error) {
        setMessage(error.message);
      } else {
        setMessage("Failed to load chart.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <Button onClick={handleLoadChart} disabled={loading}>
        {loading ? "Loading chart..." : "Generate chart"}
      </Button>

      {message ? <p className="text-sm text-red-400">{message}</p> : null}

      {chart ? (
        <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">{chart.title}</h2>

          {chart.data.length === 0 ? (
            <p className="text-sm text-white/60">No chart data available.</p>
          ) : (
            <div className="h-[360px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart.data}>
                  <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.15} />
                  <XAxis
                    dataKey={chart.x_key}
                    tick={{ fill: "#9ca3af", fontSize: 12 }}
                    interval={0}
                    angle={-20}
                    textAnchor="end"
                    height={70}
                  />
                  <YAxis tick={{ fill: "#9ca3af", fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey={chart.y_key} radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
"use client";

import Link from "next/link";
import { Sparkles, Lock } from "lucide-react";

interface Props {
  feature?: string;
  message?: string;
  /** Show a compact inline version instead of a full card */
  inline?: boolean;
}

const FEATURE_LABELS: Record<string, { title: string; description: string }> = {
  ai_chat: {
    title: "AI Chat is a Pro feature",
    description:
      "Ask unlimited questions about your data — trends, anomalies, forecasts — answered instantly by Claude.",
  },
  ai_story: {
    title: "AI Data Story is a Pro feature",
    description:
      "Generate a polished 5-slide narrative from your analysis results, ready to share with stakeholders.",
  },
  projects: {
    title: "Project limit reached",
    description:
      "Free plan includes 3 projects. Upgrade to Pro for unlimited projects and larger file support.",
  },
  file_size: {
    title: "File too large for your plan",
    description:
      "Your file exceeds the free plan's 10 MB limit. Upgrade to Pro for up to 100 MB, or Team for 500 MB.",
  },
};

export function UpgradeWall({ feature, message, inline = false }: Props) {
  const info = feature ? FEATURE_LABELS[feature] : null;
  const title = info?.title ?? "This feature requires an upgrade";
  const description = message ?? info?.description ?? "Upgrade your plan to unlock this feature.";

  if (inline) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-indigo-500/20 bg-indigo-500/5 px-4 py-3">
        <Lock className="h-4 w-4 flex-shrink-0 text-indigo-400" />
        <p className="text-sm text-white/70 flex-1">{description}</p>
        <Link
          href="/billing"
          className="flex-shrink-0 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 transition-colors"
        >
          Upgrade
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-8 text-center space-y-4">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-indigo-500/10">
        <Sparkles className="h-6 w-6 text-indigo-400" />
      </div>
      <div className="space-y-1">
        <h3 className="text-base font-semibold text-white">{title}</h3>
        <p className="text-sm text-white/50 max-w-sm">{description}</p>
      </div>
      <Link
        href="/billing"
        className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
      >
        <Sparkles className="h-4 w-4" />
        View plans
      </Link>
    </div>
  );
}

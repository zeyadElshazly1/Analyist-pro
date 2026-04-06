"use client";

import { useState } from "react";
import { Sparkles, ChevronLeft, ChevronRight, Copy, Check, Loader2 } from "lucide-react";
import { generateStory } from "@/lib/api";
import type { DataStory, StorySlide } from "@/lib/api";

interface Props {
  analysisId: number | null;
}

const SLIDE_COLORS = [
  "from-indigo-500/20 to-violet-500/10 border-indigo-500/20",
  "from-blue-500/20 to-cyan-500/10 border-blue-500/20",
  "from-emerald-500/20 to-teal-500/10 border-emerald-500/20",
  "from-amber-500/20 to-orange-500/10 border-amber-500/20",
  "from-rose-500/20 to-pink-500/10 border-rose-500/20",
];

function SlideCard({ slide, index }: { slide: StorySlide; index: number }) {
  const [copied, setCopied] = useState(false);

  function copySlide() {
    const text = `${slide.title}\n\n${slide.narrative}\n\n${slide.key_points.map((p) => `• ${p}`).join("\n")}`;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const colorClass = SLIDE_COLORS[index % SLIDE_COLORS.length];

  return (
    <div className={`relative h-full rounded-2xl border bg-gradient-to-br p-8 ${colorClass}`}>
      {/* Slide number */}
      <span className="absolute right-5 top-5 text-xs font-mono text-white/25">
        {slide.slide_num} / 5
      </span>

      {/* Copy button */}
      <button
        onClick={copySlide}
        className="absolute left-5 top-5 flex items-center gap-1 rounded-lg border border-white/10 px-2 py-1 text-[11px] text-white/40 transition-colors hover:text-white/70"
      >
        {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
        {copied ? "Copied" : "Copy"}
      </button>

      {/* Content */}
      <div className="mt-8 flex h-[calc(100%-4rem)] flex-col justify-center">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-white/40">
          Slide {slide.slide_num}
        </p>
        <h2 className="mb-4 text-2xl font-bold text-white">{slide.title}</h2>
        <p className="mb-6 text-sm leading-relaxed text-white/70">{slide.narrative}</p>

        <ul className="space-y-2">
          {slide.key_points.map((point, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-white/80">
              <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-current opacity-60" />
              {point}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function DataStoryView({ analysisId }: Props) {
  const [story, setStory] = useState<DataStory | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [currentSlide, setCurrentSlide] = useState(0);

  async function handleGenerate() {
    if (!analysisId) {
      setError("Run analysis first to generate a story.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await generateStory(analysisId);
      setStory(result);
      setCurrentSlide(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Story generation failed");
    } finally {
      setLoading(false);
    }
  }

  if (!story) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20">
          <Sparkles className="h-8 w-8 text-indigo-400" />
        </div>
        <h2 className="mb-2 text-xl font-semibold text-white">AI Data Story</h2>
        <p className="mb-8 max-w-sm text-sm text-white/50">
          Turn your analysis into a compelling 5-slide narrative powered by Claude.
          Each slide covers a key aspect of your data insights.
        </p>
        {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
        <button
          onClick={handleGenerate}
          disabled={loading || !analysisId}
          className="flex items-center gap-2 rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating story…
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Generate Data Story
            </>
          )}
        </button>
        {!analysisId && (
          <p className="mt-3 text-xs text-white/30">Run an analysis first to enable this feature.</p>
        )}
      </div>
    );
  }

  const slide = story.slides[currentSlide];
  const canPrev = currentSlide > 0;
  const canNext = currentSlide < story.slides.length - 1;

  return (
    <div className="space-y-4">
      {/* Story title */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">{story.title}</h2>
          <p className="text-xs text-white/40">{story.slides.length} slides</p>
        </div>
        <button
          onClick={() => { setStory(null); setCurrentSlide(0); }}
          className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/50 hover:text-white transition-colors"
        >
          Regenerate
        </button>
      </div>

      {/* Slide */}
      <div className="h-80">
        <SlideCard slide={slide} index={currentSlide} />
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setCurrentSlide((s) => s - 1)}
          disabled={!canPrev}
          className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs text-white/50 transition-colors hover:text-white disabled:opacity-30"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Previous
        </button>

        {/* Progress dots */}
        <div className="flex items-center gap-1.5">
          {story.slides.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrentSlide(i)}
              className={`h-1.5 rounded-full transition-all ${
                i === currentSlide ? "w-4 bg-indigo-400" : "w-1.5 bg-white/20 hover:bg-white/40"
              }`}
            />
          ))}
        </div>

        <button
          onClick={() => setCurrentSlide((s) => s + 1)}
          disabled={!canNext}
          className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs text-white/50 transition-colors hover:text-white disabled:opacity-30"
        >
          Next
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

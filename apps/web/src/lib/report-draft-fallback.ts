/**
 * Deterministic executive summary for Report Builder — mirrors backend
 * `executive_summary_draft.py` for local fallback when the API is unavailable.
 */

export type FallbackInsight = {
  insight_id?: string;
  title?: string;
  explanation?: string;
  finding?: string;
  severity?: string;
  category?: string;
  report_safe?: boolean;
  confidence?: number;
  columns_used?: string[];
  evidence?: string;
  recommendation?: string;
  why_it_matters?: string;
  caveats?: string[] | string;
};

export type ExecutiveSummaryRichInput = {
  narrative?: string | null;
  insights?: FallbackInsight[];
  datasetSummary?: {
    rows?: number;
    columns?: number;
    numeric_cols?: number;
    categorical_cols?: number;
  } | null;
  healthTotal?: number | null;
  healthResult?: {
    health_score?: { grade?: string; total_score?: number };
  } | null;
  cleaningResult?: {
    cleaning_summary?: { steps_applied?: number };
    suspicious_columns?: unknown[];
  } | null;
  compareResult?: {
    summary_draft?: string;
    row_volume_changes?: { count_a?: number; count_b?: number; diff?: number };
  } | null;
  executivePanel?: {
    opportunities?: Array<{ title?: string; summary?: string; severity?: string }>;
    risks?: Array<{ title?: string; summary?: string; severity?: string }>;
    action_plan?: Array<{ action?: string; title?: string; reason?: string }>;
  } | null;
};

/** @deprecated Use ExecutiveSummaryRichInput */
export type ExecutiveSummaryInput = ExecutiveSummaryRichInput;

export type SelectionKey = string | number;

export function selectionKeyFor(ins: FallbackInsight, idx: number): SelectionKey {
  return typeof ins.insight_id === "string" && ins.insight_id ? ins.insight_id : idx;
}

function severityRank(ins: FallbackInsight): number {
  const s = (ins.severity ?? "").toLowerCase();
  if (s === "high") return 0;
  if (s === "medium") return 1;
  if (s === "low") return 2;
  return 3;
}

function isDqCategory(ins: FallbackInsight): boolean {
  const c = (ins.category ?? "").toLowerCase();
  return c === "data_quality" || c === "missing_pattern";
}

/** Same rules as backend `select_default_insight_selection` (3–5 keys). */
export function selectRecommendedInsightKeys(
  insights: FallbackInsight[],
  opts?: { minSel?: number; maxSel?: number },
): SelectionKey[] {
  const minSel = opts?.minSel ?? 3;
  const maxSel = opts?.maxSel ?? 5;
  if (!insights.length) return [];

  const entries = insights.map((ins, i) => [i, ins] as const);
  const hasAnySafe = entries.some(([, ins]) => ins.report_safe === true);

  const picked: Array<[number, FallbackInsight]> = [];
  const pickedIdx = new Set<number>();

  function addEntry(i: number, ins: FallbackInsight): void {
    if (!pickedIdx.has(i) && picked.length < maxSel) {
      pickedIdx.add(i);
      picked.push([i, ins]);
    }
  }

  if (hasAnySafe) {
    for (const [i, ins] of entries) {
      if (ins.report_safe === true) {
        addEntry(i, ins);
        if (picked.length >= maxSel) break;
      }
    }
    if (picked.length < minSel) {
      const rest = entries
        .filter(
          ([i, ins]) =>
            !pickedIdx.has(i) &&
            !isDqCategory(ins) &&
            ["high", "medium"].includes((ins.severity ?? "").toLowerCase()),
        )
        .sort((a, b) => severityRank(a[1]) - severityRank(b[1]) || a[0] - b[0]);
      for (const [i, ins] of rest) {
        addEntry(i, ins);
        if (picked.length >= minSel) break;
      }
    }
    if (picked.length < minSel) {
      const rest = entries
        .filter(
          ([i, ins]) =>
            !pickedIdx.has(i) && ["high", "medium"].includes((ins.severity ?? "").toLowerCase()),
        )
        .sort((a, b) => severityRank(a[1]) - severityRank(b[1]) || a[0] - b[0]);
      for (const [i, ins] of rest) {
        addEntry(i, ins);
        if (picked.length >= minSel) break;
      }
    }
    if (picked.length < minSel) {
      for (const [i, ins] of entries) {
        addEntry(i, ins);
        if (picked.length >= minSel) break;
      }
    }
  } else {
    const rest = entries
      .filter(
        ([i, ins]) =>
          !isDqCategory(ins) && ["high", "medium"].includes((ins.severity ?? "").toLowerCase()),
      )
      .sort((a, b) => severityRank(a[1]) - severityRank(b[1]) || a[0] - b[0]);
    for (const [i, ins] of rest) {
      addEntry(i, ins);
      if (picked.length >= maxSel) break;
    }
    if (!picked.length) {
      for (const [i, ins] of entries.slice(0, maxSel)) addEntry(i, ins);
    } else if (picked.length < minSel) {
      for (const [i, ins] of entries) {
        if (!pickedIdx.has(i)) {
          addEntry(i, ins);
          if (picked.length >= minSel) break;
        }
      }
    }
  }

  return picked.map(([i, ins]) => selectionKeyFor(ins, i));
}

// ── Structured executive summary (backend parity) ───────────────────────────

const GENERIC_SUBSTRINGS = [
  "valuable insights",
  "this dataset provides",
  "dataset provides valuable",
  "comprehensive overview",
  "key takeaways",
  "delve deeper",
  "unlock the potential",
  "sheds light on",
  "important patterns",
  "wealth of information",
  "robust analysis shows",
] as const;

const MIN_STRONG_NARRATIVE_CHARS = 160;

function narrativeShouldUseAsIs(narrative: string): boolean {
  const s = narrative.trim();
  if (s.length < MIN_STRONG_NARRATIVE_CHARS) return false;
  const low = s.toLowerCase();
  return !GENERIC_SUBSTRINGS.some((g) => low.includes(g));
}

function severityRankVal(ins: FallbackInsight): number {
  const sev = (ins.severity ?? "").toLowerCase();
  if (sev === "critical") return 0;
  if (sev === "high") return 1;
  if (sev === "medium") return 2;
  if (sev === "low") return 3;
  return 4;
}

function insightBody(ins: FallbackInsight): string {
  for (const k of ["title", "explanation", "finding"] as const) {
    const v = ins[k];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return "";
}

function columnsPhrase(ins: FallbackInsight): string {
  const cols = ins.columns_used;
  if (!Array.isArray(cols) || !cols.length) return "";
  const clean = cols.slice(0, 4).filter(Boolean).map(String);
  if (clean.length === 1) return clean[0];
  return `${clean.slice(0, -1).join(", ")}, and ${clean[clean.length - 1]}`;
}

function topInsights(raw: FallbackInsight[], limit: number): FallbackInsight[] {
  const sorted = [...raw].sort(
    (a, b) => severityRankVal(a) - severityRankVal(b) || insightBody(b).length - insightBody(a).length,
  );
  return sorted.slice(0, limit);
}

function healthGradeAndScore(input: ExecutiveSummaryRichInput): {
  grade: string | null;
  score: number | null;
} {
  const hr = input.healthResult;
  if (hr?.health_score && typeof hr.health_score.total_score === "number") {
    return {
      grade: hr.health_score.grade != null ? String(hr.health_score.grade) : null,
      score: hr.health_score.total_score,
    };
  }
  if (input.healthTotal != null && Number.isFinite(input.healthTotal)) {
    return { grade: null, score: Number(input.healthTotal) };
  }
  return { grade: null, score: null };
}

function qualityVerdictSentence(grade: string | null, score: number | null): string {
  if (score != null) {
    const rounded = Math.round(score);
    const g = grade ? ` (grade ${grade})` : "";
    let tail: string;
    if (rounded >= 80) {
      tail =
        "structure and completeness look strong for client-facing reporting, subject to the caveats below.";
    } else if (rounded >= 60) {
      tail = "shows moderate quality — review flagged issues before wide distribution.";
    } else {
      tail = "indicates material quality issues; treat findings as directional until data is improved.";
    }
    return `Data quality score is ${rounded}/100${g}; this ${tail}`;
  }
  if (grade) {
    return `Data quality grade is ${grade}; validate key fields before acting on quantitative conclusions.`;
  }
  return "Data quality metrics were limited; confirm critical fields manually before strategic decisions.";
}

function cleaningClause(input: ExecutiveSummaryRichInput): string {
  const cr = input.cleaningResult;
  if (!cr || typeof cr !== "object") return "";
  const parts: string[] = [];
  const steps = cr.cleaning_summary?.steps_applied;
  if (typeof steps === "number" && steps > 0) {
    parts.push(`${steps} cleaning step(s) were applied in the pipeline.`);
  }
  const sus = cr.suspicious_columns;
  if (Array.isArray(sus) && sus.length) {
    parts.push(`${sus.length} column(s) were flagged for review during cleaning.`);
  }
  return parts.join(" ");
}

function compareClause(input: ExecutiveSummaryRichInput): string {
  const comp = input.compareResult;
  if (!comp || typeof comp !== "object") return "";
  if (typeof comp.summary_draft === "string" && comp.summary_draft.trim()) {
    return comp.summary_draft.trim().slice(0, 400);
  }
  const rv = comp.row_volume_changes;
  if (rv && typeof rv === "object") {
    const a = rv.count_a;
    const b = rv.count_b;
    const diff = rv.diff;
    if (typeof a === "number" && typeof b === "number") {
      let extra = "";
      if (typeof diff === "number" && diff !== 0) {
        extra = ` Net row change: ${diff > 0 ? "+" : ""}${diff.toLocaleString()}.`;
      }
      return `Comparison context: baseline file has ${a.toLocaleString()} rows; comparison file has ${b.toLocaleString()} rows.${extra}`;
    }
  }
  return "";
}

function formatFindingLine(ins: FallbackInsight): string {
  const body = insightBody(ins);
  if (!body) return "";
  const sev = (ins.severity ?? "").toLowerCase();
  const sevLbl = sev ? `${sev.charAt(0).toUpperCase() + sev.slice(1)}-severity: ` : "";
  const cols = columnsPhrase(ins);
  const ev = typeof ins.evidence === "string" ? ins.evidence.trim() : "";
  let line = `${sevLbl}${body}`;
  if (cols) line += ` (fields involved: ${cols})`;
  if (ev) line += ` Supporting context: ${ev.length > 220 ? `${ev.slice(0, 220)}…` : ev}`;
  const causal = /\b(causes?|caused|causing|proves?|proof that)\b/i;
  if (!causal.test(line)) {
    line +=
      " This pattern is associated with the fields above—not established as a root cause without further validation.";
  } else {
    line +=
      " Interpret with care: the source wording may imply causation that observational data alone cannot support.";
  }
  return line;
}

function executivePanelParts(input: ExecutiveSummaryRichInput): { impl: string; rec: string } {
  const ep = input.executivePanel;
  if (!ep || typeof ep !== "object") return { impl: "", rec: "" };

  const implications: string[] = [];
  for (const bucket of ["opportunities", "risks"] as const) {
    const items = ep[bucket];
    if (!Array.isArray(items)) continue;
    for (const it of items.slice(0, 2)) {
      if (!it || typeof it !== "object") continue;
      const t = it.title ?? it.summary;
      if (typeof t === "string" && t.trim()) implications.push(t.trim().slice(0, 280));
      if (implications.length >= 2) break;
    }
    if (implications.length >= 2) break;
  }

  let impl = "";
  if (implications.length) {
    impl = `From a business perspective, the strongest themes are: ${implications
      .slice(0, 2)
      .map((s) => `«${s}»`)
      .join(" ")} These describe associations and concentrations in the data rather than proven causal drivers.`;
  }

  let rec = "";
  const actions = ep.action_plan;
  if (Array.isArray(actions) && actions[0] && typeof actions[0] === "object") {
    const first = actions[0];
    const act = first.action ?? first.title;
    const reason = first.reason;
    if (typeof act === "string" && act.trim()) {
      rec = `Recommended next step: ${act.trim().slice(0, 320)}`;
      if (typeof reason === "string" && reason.trim()) {
        rec += ` Rationale: ${reason.trim().slice(0, 200)}`;
      }
    }
  }
  return { impl, rec };
}

function fallbackRecommendation(top: FallbackInsight[]): string {
  for (const ins of top) {
    if (typeof ins.recommendation === "string" && ins.recommendation.trim()) {
      return `Recommended next step: ${ins.recommendation.trim().slice(0, 400)}`;
    }
    if (typeof ins.why_it_matters === "string" && ins.why_it_matters.trim()) {
      return `Recommended next step: Prioritise follow-up on the highest-severity finding first — ${ins.why_it_matters.trim().slice(0, 280)}`;
    }
  }
  return (
    "Recommended next step: Review the detailed findings section with stakeholders, " +
    "validate data definitions, and agree on one measurable follow-up (e.g. retention pilot or pricing test) " +
    "before scaling any initiative."
  );
}

function caveatsSentence(insights: FallbackInsight[]): string {
  const caveats: string[] = [];
  for (const ins of insights) {
    const c = ins.caveats;
    if (Array.isArray(c)) {
      for (const item of c.slice(0, 2)) {
        if (typeof item === "string" && item.trim()) caveats.push(item.trim().slice(0, 200));
      }
    } else if (typeof c === "string" && c.trim()) caveats.push(c.trim().slice(0, 200));
    if (caveats.length >= 3) break;
  }
  const unsafe = insights.filter((i) => i.report_safe === false);
  const bits: string[] = [];
  if (caveats.length) bits.push(`Notable caveats: ${caveats.slice(0, 3).join("; ")}.`);
  if (unsafe.length) {
    bits.push(
      "Some findings above are not marked report-safe for external use — have an analyst review wording before client delivery.",
    );
  }
  return bits.join(" ");
}

function buildStructuredExecutiveSummary(input: ExecutiveSummaryRichInput): string {
  const paragraphs: string[] = [];

  const ds = input.datasetSummary;
  const rows = ds?.rows;
  const cols = ds?.columns;
  const numC = ds?.numeric_cols;
  const catC = ds?.categorical_cols;

  const bits: string[] = [];
  if (typeof rows === "number") bits.push(`${rows.toLocaleString()} rows`);
  if (typeof cols === "number") bits.push(`${cols} columns`);

  let context = "The working dataset";
  if (bits.length) {
    context += ` contains ${bits.join(" and ")}`;
    if (typeof numC === "number" && typeof catC === "number") {
      context += ` (about ${numC} numeric and ${catC} categorical fields)`;
    }
  } else {
    context += " was analyzed";
  }
  context += ".";
  const cc = compareClause(input);
  if (cc) context += ` ${cc}`;
  paragraphs.push(context);

  const { grade, score } = healthGradeAndScore(input);
  let qLine = qualityVerdictSentence(grade, score);
  const clean = cleaningClause(input);
  if (clean) qLine += ` ${clean}`;
  paragraphs.push(qLine);

  const raw = input.insights ?? [];
  const top = topInsights(raw, 3);

  if (top.length) {
    const findingLines: string[] = [];
    for (const ins of top) {
      const fl = formatFindingLine(ins);
      if (fl) findingLines.push(fl);
    }
    if (findingLines.length) {
      paragraphs.push(`Key signals from the analysis:\n• ${findingLines.join("\n• ")}`);
    } else {
      paragraphs.push(
        "Structured findings were present but could not be summarised automatically — review the Findings tab and paste the key points you want executives to see.",
      );
    }
  } else {
    paragraphs.push(
      "No ranked findings were available for automatic summary. Open the Findings tab to enrich this report once insights are generated.",
    );
  }

  const { impl, rec: epRec } = executivePanelParts(input);
  const rec = epRec || fallbackRecommendation(top);
  const bizBits = [impl, rec].filter(Boolean);
  paragraphs.push(bizBits.join(" "));

  const cav = caveatsSentence(top);
  if (cav) paragraphs.push(cav);

  return paragraphs.filter((p) => p.trim()).join("\n\n").slice(0, 8000);
}

export function buildDeterministicExecutiveSummary(input: ExecutiveSummaryRichInput): string {
  const narrative = (input.narrative ?? "").trim();
  if (narrativeShouldUseAsIs(narrative)) return narrative.slice(0, 8000);
  return buildStructuredExecutiveSummary(input);
}

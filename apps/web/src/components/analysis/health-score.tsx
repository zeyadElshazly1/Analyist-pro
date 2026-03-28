type Breakdown = {
  completeness: number;
  uniqueness: number;
  consistency: number;
  validity: number;
  structure: number;
};

type Props = {
  score: {
    total?: number;
    score?: number;
    grade?: string;
    label?: string;
    color?: string;
    breakdown?: Breakdown;
    deductions?: string[];
  };
};

function getMeta(value: number) {
  if (value >= 85) return { ring: "#4ade80", label: "Excellent quality", text: "text-emerald-400" };
  if (value >= 70) return { ring: "#60a5fa", label: "Good quality", text: "text-blue-400" };
  if (value >= 55) return { ring: "#fbbf24", label: "Needs review", text: "text-amber-400" };
  if (value >= 40) return { ring: "#f97316", label: "Poor quality", text: "text-orange-400" };
  return { ring: "#f87171", label: "Critical issues", text: "text-red-400" };
}

export function HealthScore({ score }: Props) {
  const value = score?.total ?? score?.score ?? 0;
  const grade = score?.grade ?? "–";
  const breakdown = score?.breakdown;
  const deductions = score?.deductions ?? [];
  const meta = getMeta(value);

  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;

  const subScores = breakdown
    ? [
        { label: "Completeness", value: breakdown.completeness, max: 30 },
        { label: "Uniqueness", value: breakdown.uniqueness, max: 20 },
        { label: "Consistency", value: breakdown.consistency, max: 20 },
        { label: "Validity", value: breakdown.validity, max: 15 },
        { label: "Structure", value: breakdown.structure, max: 15 },
      ]
    : [];

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative flex-shrink-0">
          <svg width="88" height="88" viewBox="0 0 88 88" className="-rotate-90">
            <circle
              cx="44" cy="44" r={radius}
              fill="none"
              stroke="rgba(255,255,255,0.06)"
              strokeWidth="6"
            />
            <circle
              cx="44" cy="44" r={radius}
              fill="none"
              stroke={meta.ring}
              strokeWidth="6"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              strokeLinecap="round"
              style={{ transition: "stroke-dashoffset 0.6s ease" }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-lg font-bold text-white">{value}</span>
            <span className="text-[10px] text-white/40">/100</span>
          </div>
        </div>

        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <p className="text-base font-semibold text-white">Dataset health score</p>
            <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-white/60">
              Grade {grade}
            </span>
          </div>
          <p className={`text-sm font-medium ${meta.text}`}>{meta.label}</p>
          <p className="text-xs text-white/40">
            Based on completeness, uniqueness, consistency, validity & structure
          </p>
        </div>
      </div>

      {subScores.length > 0 && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          {subScores.map((s) => (
            <div key={s.label} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3">
              <p className="text-[11px] text-white/40">{s.label}</p>
              <p className="mt-1 text-sm font-semibold text-white">
                {s.value}
                <span className="text-xs font-normal text-white/30">/{s.max}</span>
              </p>
              <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-indigo-500"
                  style={{ width: `${(s.value / s.max) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {deductions.length > 0 && (
        <div className="rounded-xl border border-amber-500/15 bg-amber-500/5 p-4">
          <p className="mb-2 text-xs font-medium text-amber-400/80">Score deductions</p>
          <ul className="space-y-1">
            {deductions.map((d, i) => (
              <li key={i} className="text-xs text-white/50">· {d}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

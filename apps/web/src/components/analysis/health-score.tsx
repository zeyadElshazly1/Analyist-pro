type Props = {
    score: {
      score?: number;
      grade?: string;
    };
  };
  
  function getScoreMeta(value: number) {
    if (value >= 80) {
      return {
        color: "bg-green-500 text-black",
        label: "Strong quality",
      };
    }
  
    if (value >= 50) {
      return {
        color: "bg-yellow-400 text-black",
        label: "Needs review",
      };
    }
  
    return {
      color: "bg-red-500 text-black",
      label: "Low quality",
    };
  }
  
  export function HealthScore({ score }: Props) {
    const value = score?.score ?? 0;
    const grade = score?.grade ?? "N/A";
    const meta = getScoreMeta(value);
  
    return (
      <div className="flex flex-col gap-4 md:flex-row md:items-center">
        <div
          className={`flex h-16 w-16 items-center justify-center rounded-full text-xl font-bold ${meta.color}`}
        >
          {value}
        </div>
  
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-lg font-semibold text-white">Dataset health score</p>
            <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-white/70">
              Grade {grade}
            </span>
          </div>
  
          <p className="text-sm text-white/60">
            Quality based on missing values, types, and consistency
          </p>
  
          <p className="text-sm text-white">{meta.label}</p>
        </div>
      </div>
    );
  }
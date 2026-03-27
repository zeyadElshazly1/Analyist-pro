type ColumnProfile = {
    column?: string;
    dtype?: string;
    missing_pct?: number;
    unique_values?: number;
    sample_values?: string[];
  };
  
  type Props = {
    profile: ColumnProfile[];
  };
  
  export function ColumnsTable({ profile }: Props) {
    if (!profile || profile.length === 0) {
      return <p className="text-sm text-white/60">No column profile available.</p>;
    }
  
    return (
      <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/5">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm text-white">
            <thead className="border-b border-white/10 bg-white/5 text-white/60">
              <tr>
                <th className="px-4 py-3 font-medium">Column</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Missing %</th>
                <th className="px-4 py-3 font-medium">Unique</th>
                <th className="px-4 py-3 font-medium">Sample</th>
              </tr>
            </thead>
  
            <tbody>
              {profile.map((col, idx) => (
                <tr key={`${col.column}-${idx}`} className="border-b border-white/10 last:border-b-0">
                  <td className="px-4 py-3 font-medium">{col.column ?? "—"}</td>
                  <td className="px-4 py-3 text-white/70">{col.dtype ?? "—"}</td>
                  <td className="px-4 py-3 text-white/70">
                    {col.missing_pct ?? 0}
                  </td>
                  <td className="px-4 py-3 text-white/70">
                    {col.unique_values ?? "—"}
                  </td>
                  <td className="max-w-[260px] truncate px-4 py-3 text-white/50">
                    {Array.isArray(col.sample_values) && col.sample_values.length > 0
                      ? col.sample_values.join(", ")
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }
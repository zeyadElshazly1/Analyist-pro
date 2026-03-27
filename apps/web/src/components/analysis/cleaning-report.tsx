type CleaningItem =
  | string
  | {
      column?: string;
      action?: string;
      details?: string;
      before?: string | number;
      after?: string | number;
    };

type Props = {
  items: CleaningItem[];
};

function renderItem(item: CleaningItem, idx: number) {
  if (typeof item === "string") {
    return (
      <div
        key={idx}
        className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-white/80"
      >
        {item}
      </div>
    );
  }

  return (
    <div
      key={idx}
      className="rounded-xl border border-white/10 bg-white/5 p-4"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-white">
          {item.action ?? "Cleaning action"}
        </span>

        {item.column ? (
          <span className="text-sm font-medium text-white">
            {item.column}
          </span>
        ) : null}
      </div>

      {item.details ? (
        <p className="mt-2 text-sm text-white/70">{item.details}</p>
      ) : null}

      {(item.before !== undefined || item.after !== undefined) ? (
        <div className="mt-2 flex flex-wrap gap-4 text-xs text-white/50">
          {item.before !== undefined ? <span>Before: {String(item.before)}</span> : null}
          {item.after !== undefined ? <span>After: {String(item.after)}</span> : null}
        </div>
      ) : null}
    </div>
  );
}

export function CleaningReport({ items }: Props) {
  if (!items || items.length === 0) {
    return <p className="text-sm text-white/60">No cleaning actions recorded.</p>;
  }

  return <div className="space-y-3">{items.map(renderItem)}</div>;
}
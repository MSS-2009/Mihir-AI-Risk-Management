"use client";
// Tornado, which assumption moves the answer most. Horizontal bars diverging
// from a baseline, sorted by magnitude.

export function TornadoChart({
  rows,
  unit = "",
}: {
  rows: { label: string; low: number; high: number }[];
  unit?: string;
}) {
  if (!rows.length) return null;
  const maxAbs = Math.max(...rows.map((r) => Math.max(Math.abs(r.low), Math.abs(r.high))), 1);
  const sorted = [...rows].sort(
    (a, b) => Math.max(Math.abs(b.low), Math.abs(b.high)) - Math.max(Math.abs(a.low), Math.abs(a.high))
  );

  return (
    <div className="space-y-2.5">
      {sorted.map((r) => {
        const lw = (Math.abs(Math.min(r.low, 0)) / maxAbs) * 50;
        const hw = (Math.abs(Math.max(r.high, 0)) / maxAbs) * 50;
        return (
          <div key={r.label} className="grid grid-cols-[1fr_2fr] items-center gap-3">
            <div className="truncate text-right text-xs text-muted">{r.label}</div>
            <div className="relative flex h-5 items-center">
              <div className="absolute left-1/2 top-0 h-full w-px bg-rule" />
              <div className="flex w-1/2 justify-end">
                <div className="h-3.5 rounded-l bg-amber/70" style={{ width: `${lw}%` }} title={`${unit}${r.low}`} />
              </div>
              <div className="flex w-1/2 justify-start">
                <div className="h-3.5 rounded-r bg-brand/70" style={{ width: `${hw}%` }} title={`${unit}${r.high}`} />
              </div>
            </div>
          </div>
        );
      })}
      <div className="grid grid-cols-[1fr_2fr] gap-3 pt-1 font-mono text-[0.62rem] text-muted">
        <span />
        <div className="flex justify-between">
          <span>← lowers exposure</span>
          <span>raises exposure →</span>
        </div>
      </div>
    </div>
  );
}

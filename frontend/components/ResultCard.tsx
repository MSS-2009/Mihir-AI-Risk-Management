import { money, pct } from "@/lib/format";

/** Expected value, range, and probability, together. Never the point estimate alone. */
export function ResultCard({
  label,
  expected,
  low,
  high,
  lowLabel = "P10",
  highLabel = "P90",
  probability,
  probabilityLabel,
  tone = "bordeaux",
}: {
  label: string;
  expected: number;
  low: number;
  high: number;
  lowLabel?: string;
  highLabel?: string;
  probability?: number;
  probabilityLabel?: string;
  tone?: "bordeaux" | "ochre";
}) {
  const accent = tone === "ochre" ? "text-amber" : "text-brand";
  return (
    <div className="rounded-xl border border-rule bg-surface p-5 shadow-card">
      <div className="eyebrow">{label}</div>
      <div className={`mt-1.5 font-display text-3xl font-semibold tabular-nums ${accent}`}>
        {money(expected)}
      </div>
      <div className="mt-3 flex items-center gap-2 font-mono text-xs text-muted tnum">
        <span>{lowLabel} {money(low)}</span>
        <span className="h-px flex-1 bg-rule" />
        <span>{highLabel} {money(high)}</span>
      </div>
      {probability !== undefined && (
        <div className="mt-3 text-sm text-ink/80 tnum">
          <span className={`font-semibold ${accent}`}>{pct(probability)}</span>{" "}
          {probabilityLabel || "probability"}
        </div>
      )}
    </div>
  );
}

/** Compact stat for grids. */
export function Stat({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "ochre";
}) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div
        className={`mt-1 font-display text-2xl font-semibold tabular-nums ${
          tone === "ochre" ? "text-amber" : "text-ink"
        }`}
      >
        {value}
      </div>
      {sub && <div className="mt-0.5 font-mono text-[0.68rem] text-muted tnum">{sub}</div>}
    </div>
  );
}

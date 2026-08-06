"use client";
import type { PricedDecision } from "@/lib/api";
import { money, moneyCompact } from "@/lib/format";

/**
 * Where the exposure goes if you act. Starts at today's expected annual loss,
 * subtracts each decision that pays for itself, and lands on what is left.
 *
 * This is the single most useful picture on the page because it answers the
 * only question that matters: if I do the things you recommend, what changes?
 */
export function ExposureWaterfall({
  baseline,
  decisions,
  height = 220,
}: {
  baseline: number;
  decisions: PricedDecision[];
  height?: number;
}) {
  const worth = decisions.filter((d) => d.npv > 0);
  const steps = worth.map((d) => ({ label: d.title, value: d.expected_saving_annual }));
  const residual = Math.max(0, baseline - steps.reduce((s, x) => s + x.value, 0));
  const span = baseline || 1;

  // Cumulative positions so each bar floats where the previous one ended.
  let running = baseline;
  const bars = [
    { label: "Today", bottom: 0, size: baseline, kind: "base" as const, value: baseline },
    ...steps.map((s) => {
      const bottom = running - s.value;
      running = bottom;
      return { label: s.label, bottom, size: s.value, kind: "cut" as const, value: s.value };
    }),
    { label: "After acting", bottom: 0, size: residual, kind: "final" as const, value: residual },
  ];

  return (
    <div>
      <div className="flex items-end gap-2 sm:gap-3" style={{ height }}>
        {bars.map((b, i) => {
          const h = Math.max(2, (b.size / span) * 100);
          const off = (b.bottom / span) * 100;
          const cls =
            b.kind === "base" ? "bg-ink/80" : b.kind === "final" ? "bg-brand" : "bg-emerald";
          return (
            <div key={i} className="relative flex h-full flex-1 flex-col justify-end">
              <span className="mb-1 text-center font-mono text-[0.6rem] tabular-nums text-ink">
                {b.kind === "cut" ? `-${moneyCompact(b.value)}` : moneyCompact(b.value)}
              </span>
              <div className="relative w-full flex-1">
                <div
                  className={`absolute w-full rounded-sm ${cls}`}
                  style={{ height: `${h}%`, bottom: `${off}%` }}
                  title={`${b.label}: ${money(b.value)}`}
                />
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex gap-2 sm:gap-3">
        {bars.map((b, i) => (
          <div key={i} className="flex-1 text-center">
            <span className="line-clamp-2 font-mono text-[0.55rem] leading-tight text-muted">
              {b.kind === "cut" ? b.label.split(" ").slice(0, 3).join(" ") : b.label}
            </span>
          </div>
        ))}
      </div>
      {worth.length === 0 && (
        <p className="mt-3 text-xs text-muted">
          None of the available actions currently pays for itself at these estimates. That is a
          result, not a gap: it says your exposure is cheaper to carry than to remove.
        </p>
      )}
    </div>
  );
}

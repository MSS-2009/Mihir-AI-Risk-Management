"use client";
import type { RobustnessResponse } from "@/lib/api";
import { money, pct } from "@/lib/format";

/**
 * The highest-value output in the product. It tells an operator exactly which
 * single assumption to spend effort refining, and by implication which ones
 * they can safely leave alone.
 *
 * We claim robustness, never accuracy: robustness is a visible computation,
 * accuracy would need years of realized-loss validation we do not have.
 */
export function FragilityPanel({
  r,
  loading,
  eps,
  onEps,
}: {
  r: RobustnessResponse | null;
  loading: boolean;
  eps: number;
  onEps: (v: number) => void;
}) {
  const top = r?.dependence_fragility?.[0];

  return (
    <div className="rounded-2xl border border-rule bg-surface p-6 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="eyebrow">What your answer rests on</div>
          <h2 className="mt-1 font-display text-xl font-bold text-ink">Dependence fragility</h2>
        </div>
        <fieldset className="flex items-center gap-1 rounded-lg border border-rule bg-raised p-0.5">
          <legend className="sr-only">How confident are you in these relationships?</legend>
          {[
            { v: 0.05, label: "Conservative" },
            { v: 0.10, label: "Moderate" },
            { v: 0.20, label: "Uncertain" },
          ].map((o) => (
            <button
              key={o.v}
              onClick={() => onEps(o.v)}
              aria-pressed={eps === o.v}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                eps === o.v ? "bg-brand text-white" : "text-muted hover:text-ink"
              }`}
            >
              {o.label}
            </button>
          ))}
        </fieldset>
      </div>

      <p className="mt-1 font-mono text-[0.62rem] uppercase tracking-wide text-muted">
        How confident are you in these relationships?
      </p>

      {loading && !r && (
        <p className="mt-5 text-sm text-muted">
          Sweeping 60 alternative dependence structures at {(50000).toLocaleString("en-US")} scenarios each...
        </p>
      )}

      {r && (
        <>
          {/* The sentence. */}
          <p className="thesis mt-5 text-[1.05rem] leading-relaxed text-ink">{r.reading}</p>

          <div className="mt-5 space-y-2.5">
            {r.dependence_fragility.slice(0, 5).map((f, i) => {
              const max = r.dependence_fragility[0].p99_swing || 1;
              return (
                <div key={f.pair.join("|")}>
                  <div className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="truncate text-ink/85">
                      <span className="font-mono text-[0.66rem] text-muted">{i + 1}</span>{" "}
                      {f.labels[0]} <span className="text-muted">x</span> {f.labels[1]}
                    </span>
                    <span className="shrink-0 font-mono text-xs tabular-nums text-muted">
                      {money(f.p99_swing)}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-rule">
                      <div
                        className={`h-full rounded-full ${f.is_default ? "bg-amber" : "bg-brand"}`}
                        style={{ width: `${Math.max(3, (f.p99_swing / max) * 100)}%` }}
                      />
                    </div>
                    <span className="w-24 shrink-0 text-right font-mono text-[0.6rem] text-muted tnum">
                      {f.is_default ? "default estimate" : `set to ${f.rho.toFixed(2)}`}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <p className="mt-4 border-t border-rule pt-3 text-xs leading-relaxed text-muted">
            Each bar is how far your P99 moves when that one relationship is shifted by 0.25 in either
            direction. Amber means the pair is still at our default estimate, which is where refining it
            buys you the most.
          </p>
        </>
      )}
    </div>
  );
}

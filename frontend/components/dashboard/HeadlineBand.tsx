"use client";
import type { Assessment, RobustnessResponse } from "@/lib/api";
import { money, moneyCompact, pct } from "@/lib/format";

/**
 * Headline figures carry a band, not a point. The point estimate alone would be
 * exactly the false precision this product exists to correct, and we happen to
 * be able to measure the uncertainty in our own dependence assumptions.
 */
export function HeadlineBand({
  a,
  r,
  loadingRobustness,
}: {
  a: Assessment;
  r: RobustnessResponse | null;
  loadingRobustness: boolean;
}) {
  const P = Object.fromEntries(a.exceedance_curve.map((e) => [e.percentile, e.loss]));
  const jb = a.joint_breach;
  const ratio = jb.three_plus_independent ? jb.three_plus / jb.three_plus_independent : 0;

  return (
    <div className="rounded-2xl border border-rule bg-surface p-6 shadow-card sm:p-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div className="eyebrow">{a.industry_name} · annual loss exposure</div>
        <div className="font-mono text-[0.66rem] text-muted tnum">
          {a.n_sims.toLocaleString("en-US")} scenarios · seed {a.seed}
        </div>
      </div>

      <div className="mt-6 grid gap-8 lg:grid-cols-[1.1fr_1fr]">
        <div>
          <Figure
            label="Expected annual loss"
            value={money(a.expected_annual_loss)}
            sub={
              a.expected_annual_loss_pct_revenue
                ? `${pct(a.expected_annual_loss_pct_revenue, 2)} of revenue`
                : undefined
            }
          />
          <div className="mt-6">
            <Figure
              label="Tail to plan against · P99"
              value={money(P[99])}
              accent
              sub={
                r
                  ? `range ${moneyCompact(r.robustness.p99_low)} to ${moneyCompact(r.robustness.p99_high)} under dependence uncertainty`
                  : loadingRobustness
                  ? "measuring the range under dependence uncertainty..."
                  : undefined
              }
            />
          </div>
          <div className="mt-6 grid grid-cols-2 gap-4">
            <Small label="P95" value={money(P[95])} />
            <Small label="If risks were independent · P99" value={money(a.exceedance_curve_independent.find((e) => e.percentile === 99)?.loss ?? 0)} />
          </div>
        </div>

        {/* The claim, stated plainly. */}
        <div className="rounded-xl border border-rule bg-raised p-5">
          <div className="eyebrow">What correlation actually does</div>
          <p className="thesis mt-3 text-[1.05rem] leading-relaxed text-ink">
            Treating these risks as independent understates your P99 by{" "}
            <span className="font-semibold text-brand tnum">{pct(a.correlation_premium.p99)}</span>.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            It barely moves the average at all: expected loss is within{" "}
            <span className="tnum">
              {pct(Math.abs(a.expected_annual_loss / a.expected_annual_loss_independent - 1), 1)}
            </span>{" "}
            either way. Correlation does not change what a typical year costs. It changes how bad the
            bad years get.
          </p>
          <div className="mt-4 border-t border-rule pt-4">
            <div className="eyebrow">Domains breaching together</div>
            <p className="mt-2 text-sm leading-relaxed text-ink/85">
              Three or more domains pass their own P90 in the same year{" "}
              <span className="font-semibold tnum text-brand">{pct(jb.three_plus, 1)}</span> of the time,
              against <span className="tnum">{pct(jb.three_plus_independent, 1)}</span> if they were
              independent
              {ratio ? (
                <>
                  , about <span className="font-semibold tnum">{ratio.toFixed(1)}x</span> as often
                </>
              ) : null}
              .
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Figure({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: boolean }) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div className={`mt-1 font-display text-4xl font-bold tabular-nums sm:text-5xl ${accent ? "text-brand" : "text-ink"}`}>
        {value}
      </div>
      {sub && <div className="mt-1.5 font-mono text-[0.7rem] text-muted tnum">{sub}</div>}
    </div>
  );
}

function Small({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-mono text-[0.6rem] uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-0.5 font-mono text-lg font-semibold tabular-nums text-ink">{value}</div>
    </div>
  );
}

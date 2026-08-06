"use client";
import { useState } from "react";
import type { PricedDecision } from "@/lib/api";
import { money, moneyCompact, pct } from "@/lib/format";

/**
 * A decision, priced. This is the unit an operator actually acts on, so it is
 * built to be scanned and judged in about three seconds: verdict, value, and
 * the cost it takes to get there.
 *
 * Deliberately visual rather than prose. The rationale is one line and folded
 * away, because a wall of explanation is what a reader skips.
 */
export function DecisionCard({ d }: { d: PricedDecision }) {
  const [open, setOpen] = useState(false);

  // Verdict is driven by the model, not by editorial choice.
  const verdict =
    d.npv > 0 && d.prob_beneficial >= 0.5
      ? { label: "Worth it", tone: "good" as const }
      : d.npv > 0 || d.prob_beneficial >= 0.35
      ? { label: "Marginal", tone: "mid" as const }
      : { label: "Not worth it", tone: "bad" as const };

  const tone = {
    good: { text: "text-emerald", bg: "bg-emerald", ring: "border-emerald/35", chip: "bg-emerald/12 text-emerald" },
    mid: { text: "text-amber", bg: "bg-amber", ring: "border-amber/35", chip: "bg-amber/12 text-amber" },
    bad: { text: "text-muted", bg: "bg-muted", ring: "border-rule", chip: "bg-rule text-muted" },
  }[verdict.tone];

  const totalCostYr = d.cost_annual + (d.cost_upfront ? d.cost_upfront / d.horizon_years : 0);
  const span = Math.max(totalCostYr, d.expected_saving_annual, 1);

  return (
    <div className={`rounded-2xl border bg-surface p-5 shadow-card transition-shadow hover:shadow-lift ${tone.ring}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <span className={`inline-block rounded-full px-2 py-0.5 font-mono text-[0.6rem] uppercase tracking-wide ${tone.chip}`}>
            {verdict.label}
          </span>
          <h3 className="mt-2 font-display text-lg font-bold leading-snug text-ink">{d.title}</h3>
        </div>
        <div className="shrink-0 text-right">
          <div className="font-mono text-[0.58rem] uppercase tracking-wide text-muted">3-yr NPV</div>
          <div className={`font-display text-2xl font-bold tabular-nums ${d.npv > 0 ? "text-emerald" : "text-ink"}`}>
            {moneyCompact(d.npv)}
          </div>
        </div>
      </div>

      {/* Cost against saving, as opposing bars. The comparison is the point. */}
      <div className="mt-4 space-y-1.5">
        <Bar label="Costs" value={totalCostYr} span={span} className="bg-ink/25" money />
        <Bar label="Saves" value={d.expected_saving_annual} span={span} className={tone.bg} money
             range={[d.saving_p10, d.saving_p90]} />
      </div>

      {/* Probability, as a filled track rather than a sentence. */}
      <div className="mt-4">
        <div className="flex items-baseline justify-between font-mono text-[0.62rem] text-muted">
          <span>WORTH IT IN</span>
          <span className={`text-sm font-semibold tabular-nums ${tone.text}`}>{pct(d.prob_beneficial)}</span>
        </div>
        <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-rule">
          <div className={`h-full rounded-full ${tone.bg}`} style={{ width: `${Math.max(1, d.prob_beneficial * 100)}%` }} />
        </div>
        <div className="mt-1 flex justify-between font-mono text-[0.55rem] text-muted">
          <span>of 50,000 scenarios</span>
          <span>break-even at 50%</span>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 border-t border-rule pt-3">
        <Stat label="Cuts P99 by" value={moneyCompact(d.p99_reduction)} />
        <Stat label="Payback" value={d.payback_years ? `${d.payback_years.toFixed(1)} yr` : "n/a"} />
        <Stat label="Effort" value={d.effort} />
      </div>

      <button
        onClick={() => setOpen((s) => !s)}
        aria-expanded={open}
        className="mt-3 font-mono text-[0.62rem] uppercase tracking-wide text-muted hover:text-brand"
      >
        {open ? "hide reasoning" : "why this number"}
      </button>
      {open && (
        <p className="mt-2 border-t border-rule pt-2 text-xs leading-relaxed text-muted">
          {d.rationale} {d.basis}
        </p>
      )}
    </div>
  );
}

function Bar({
  label, value, span, className, money: isMoney, range,
}: {
  label: string; value: number; span: number; className: string; money?: boolean;
  range?: [number, number];
}) {
  const w = Math.max(1, (value / span) * 100);
  const lo = range ? (range[0] / span) * 100 : null;
  const hi = range ? (range[1] / span) * 100 : null;
  return (
    <div className="flex items-center gap-3">
      <span className="w-12 shrink-0 font-mono text-[0.6rem] uppercase text-muted">{label}</span>
      <div className="relative h-4 flex-1 overflow-hidden rounded bg-rule/60">
        {lo !== null && hi !== null && (
          <div className="absolute inset-y-0 bg-current opacity-15" style={{ left: `${lo}%`, width: `${Math.max(1, hi - lo)}%` }} />
        )}
        <div className={`h-full rounded ${className}`} style={{ width: `${w}%` }} />
      </div>
      <span className="w-20 shrink-0 text-right font-mono text-xs tabular-nums text-ink">
        {isMoney ? money(value) : value}
      </span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-mono text-[0.55rem] uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-0.5 font-mono text-sm font-semibold capitalize tabular-nums text-ink">{value}</div>
    </div>
  );
}

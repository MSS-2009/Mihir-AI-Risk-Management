import type { Composite } from "@/lib/api";
import { money, moneyCompact, pct } from "@/lib/format";

/** The differentiator, front and center: how much worse risks are together. */
export function CompositeHeadline({ c }: { c: Composite }) {
  const max = Math.max(c.naive_sum_p95, c.correlated_p95, c.independent_p95);
  const bar = (v: number) => `${Math.max(4, (v / max) * 100)}%`;
  return (
    <div className="rounded-2xl border border-bordeaux/20 bg-gradient-to-br from-bordeaux-deep to-bordeaux p-6 text-white sm:p-8">
      <div className="font-mono text-[0.7rem] uppercase tracking-[0.18em] text-white/60">
        Composite risk · all domains
      </div>
      <h2 className="mt-3 max-w-3xl font-display text-3xl font-semibold leading-tight sm:text-4xl">
        {c.headline}
      </h2>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_1fr]">
        <div className="grid grid-cols-2 gap-6">
          <Stat2 label="Expected annual loss" value={money(c.expected_total_loss)} />
          <Stat2 label="Composite tail · P95" value={money(c.correlated_p95)} accent />
          <Stat2 label="Worse together" value={pct(c.amplification_pct)} accent />
          <Stat2 label="P99 tail" value={money(c.correlated_p99)} />
        </div>

        {/* Independent vs correlated vs naive */}
        <div className="space-y-3">
          <BarRow label="If risks were independent" value={c.independent_p95} width={bar(c.independent_p95)} tone="mist" fmt />
          <BarRow label="Correlated (reality)" value={c.correlated_p95} width={bar(c.correlated_p95)} tone="white" fmt />
          <BarRow label="Naive additive sum" value={c.naive_sum_p95} width={bar(c.naive_sum_p95)} tone="dim" fmt />
          <p className="pt-1 font-mono text-[0.66rem] text-white/50">
            P95 loss under each assumption. Reality sits between diversification and naive addition.
          </p>
        </div>
      </div>
    </div>
  );
}

function Stat2({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <div className="font-mono text-[0.62rem] uppercase tracking-wide text-white/55">{label}</div>
      <div className={`mt-1 font-display text-2xl font-semibold tabular-nums ${accent ? "text-white" : "text-white/90"}`}>
        {value}
      </div>
    </div>
  );
}

function BarRow({
  label,
  value,
  width,
  tone,
  fmt,
}: {
  label: string;
  value: number;
  width: string;
  tone: "mist" | "white" | "dim";
  fmt?: boolean;
}) {
  const color = tone === "white" ? "bg-white" : tone === "dim" ? "bg-white/25" : "bg-white/50";
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-white/75">{label}</span>
        <span className="font-mono tabular-nums text-white">{fmt ? moneyCompact(value) : value}</span>
      </div>
      <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-white/10">
        <div className={`h-full rounded-full ${color}`} style={{ width }} />
      </div>
    </div>
  );
}

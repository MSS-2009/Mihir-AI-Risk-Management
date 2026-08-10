"use client";
import { useEffect, useState } from "react";
import { getHealth, type Health } from "@/lib/api";
import { Badge, Button, Eyebrow } from "@/components/ui";

type Row = { label: string; free: boolean | string; growth: boolean | string; cont: boolean | string };

const ROWS: Row[] = [
  { label: "Industry selection and guided intake", free: true, growth: true, cont: true },
  { label: "Document upload & extraction", free: true, growth: true, cont: true },
  { label: "Every model for your industry, 50,000 scenarios", free: true, growth: true, cont: true },
  { label: "Composite correlation dashboard", free: true, growth: true, cont: true },
  { label: "Robustness band and dependence fragility", free: true, growth: true, cont: true },
  { label: "Sensitivity tornado", free: true, growth: true, cont: true },
  { label: "AI interpretation & recommendations", free: true, growth: true, cont: true },
  { label: "Executive summary / one-pager / list", free: true, growth: true, cont: true },
  { label: "Saved history", free: false, growth: true, cont: true },
  { label: "Benchmarking against peers", free: false, growth: true, cont: true },
  { label: "Scheduled connector data pulls", free: false, growth: true, cont: true },
  { label: "PDF & slide-deck export", free: false, growth: true, cont: true },
  { label: "Live read-only DB connector", free: false, growth: false, cont: true },
  { label: "Continuous re-simulation & alerting", free: false, growth: false, cont: true },
  { label: "Local agent (watches your files)", free: false, growth: false, cont: true },
];

const TIERS = [
  { id: "free", name: "Free", price: "$0", note: "Everything you need to get a defensible number.", cta: "Start free", href: "/start", highlight: false },
  { id: "growth", name: "Growth", price: "$1K", per: "/mo", note: "History, benchmarking, scheduled pulls, exports.", cta: "Coming soon", href: "/start", highlight: true },
  { id: "cont", name: "Continuous", price: "$5K", per: "/mo", note: "Live connector, continuous re-sim, alerting.", cta: "Coming soon", href: "/start", highlight: false },
];

export default function PricingPage() {
  const [health, setHealth] = useState<Health | null>(null);
  useEffect(() => {
    getHealth().then(setHealth).catch(() => {});
  }, []);

  const cell = (v: boolean | string) =>
    typeof v === "string" ? (
      <span className="text-sm text-ink">{v}</span>
    ) : v ? (
      <span className="text-brand">✓</span>
    ) : (
      <span className="text-muted">-</span>
    );

  return (
    <div className="container-x py-12">
      <div className="max-w-2xl">
        <Eyebrow>Pricing</Eyebrow>
        <h1 className="mt-2 font-display text-4xl font-bold tracking-tight text-ink">
          Analyst-grade risk, at mid-market prices.
        </h1>
        <p className="mt-3 text-muted">
          The free tier runs every model for your industry, the full composite, and the robustness layer. No account, no gate. Paid tiers add
          persistence, live data, and continuous monitoring. We&apos;re honest about what&apos;s built
          today: everything below the line is scaffolded.
        </p>
      </div>

      <div className="mt-10 grid gap-4 lg:grid-cols-3">
        {TIERS.map((t) => (
          <div
            key={t.id}
            className={`rounded-2xl border p-6 ${
              t.highlight ? "border-brand bg-brand/[0.03] shadow-card" : "border-rule bg-surface"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-display text-xl font-bold text-ink">{t.name}</span>
              {t.id === "free" && <Badge tone="bordeaux">Available now</Badge>}
            </div>
            <div className="mt-3 flex items-baseline gap-1">
              <span className="font-display text-4xl font-bold tabular-nums text-ink">{t.price}</span>
              {t.per && <span className="text-muted">{t.per}</span>}
            </div>
            <p className="mt-2 min-h-[2.5rem] text-sm text-muted">{t.note}</p>
            <div className="mt-4">
              <Button href={t.href} variant={t.highlight ? "primary" : "outline"} className="w-full">
                {t.cta}
              </Button>
            </div>
          </div>
        ))}
      </div>

      {/* Comparison */}
      <div className="mt-12 overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse text-left">
          <thead>
            <tr className="border-b border-rule">
              <th className="py-3 font-mono text-[0.66rem] uppercase tracking-wide text-muted">Capability</th>
              <th className="py-3 text-center font-mono text-[0.66rem] uppercase tracking-wide text-muted">Free</th>
              <th className="py-3 text-center font-mono text-[0.66rem] uppercase tracking-wide text-muted">Growth</th>
              <th className="py-3 text-center font-mono text-[0.66rem] uppercase tracking-wide text-muted">Continuous</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((r) => (
              <tr key={r.label} className="border-b border-rule/60">
                <td className="py-2.5 text-sm text-ink/85">{r.label}</td>
                <td className="py-2.5 text-center">{cell(r.free)}</td>
                <td className="py-2.5 text-center">{cell(r.growth)}</td>
                <td className="py-2.5 text-center">{cell(r.cont)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {health && (
        <p className="mt-6 font-mono text-[0.66rem] text-muted">
          Live build status · {health.engines} engines registered · AI interpretation{" "}
          {health.ai_enabled ? "enabled" : "in fallback mode"} · gated features are one config flag from launch.
        </p>
      )}
    </div>
  );
}

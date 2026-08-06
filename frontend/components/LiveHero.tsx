"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getShowcase, type ShowcaseIndustry, type PricedDecision } from "@/lib/api";
import { money, moneyCompact, pct } from "@/lib/format";
import { reprice } from "@/lib/reprice";
import { DistributionChart } from "@/components/charts/DistributionChart";
import { ScrollFloat, ScrollReveal } from "@/components/ScrollFloat";

/**
 * The signature element: pick an industry, then drag what the action costs and
 * watch whether it is still worth funding.
 *
 * This used to be a tariff slider, which made the whole front page an argument
 * for one of the five industries and invited every other visitor to conclude
 * the product was not for them. The lever is now the one thing every operator
 * in every industry argues about, which is the price of the fix.
 *
 * Every figure is real model output. The industry headlines come from a cached
 * server run, and repricing happens in the browser because NPV is affine in
 * cost, so dragging the slider is instant and costs the backend nothing.
 */
export function LiveHero() {
  const [data, setData] = useState<ShowcaseIndustry[] | null>(null);
  const [offline, setOffline] = useState(false);
  const [active, setActive] = useState(0);
  const [costScale, setCostScale] = useState(1);

  useEffect(() => {
    getShowcase()
      .then((r) => setData(r.industries))
      .catch(() => setOffline(true));
  }, []);

  const ind = data?.[active];
  const base = ind?.decision;

  // The slider scales the pack's cost estimate; everything else follows.
  const priced: PricedDecision | null =
    base
      ? reprice(base as PricedDecision, {
          cost_upfront: base.cost_upfront * costScale,
          cost_annual: base.cost_annual * costScale,
        })
      : null;

  const totalCost = priced ? priced.cost_upfront + priced.cost_annual * (priced.horizon_years || 3) : 0;

  return (
    <section className="border-b border-rule bg-surface">
      <div className="container-x grid items-center gap-12 py-16 lg:grid-cols-[1.05fr_1.25fr] lg:py-24">
        {/* Left: the argument */}
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-brand" />
            <span className="eyebrow">Enterprise risk quantification</span>
          </div>
          <div className="mt-5 flex gap-4">
            <span className="mt-1 hidden w-[3px] shrink-0 rounded-full bg-brand sm:block" />
            <ScrollFloat
              as="h1"
              className="font-display text-display-lg font-extrabold"
              segments={[
                { text: "Risk, priced in dollars.", className: "text-ink" },
                { text: "Not “High.” Not a color.", className: "text-brand" },
              ]}
            />
          </div>
          <ScrollReveal as="p" className="mt-6 max-w-md text-lg leading-relaxed text-muted">
            Pick your industry, then drag what the fix costs. The answer is not one number, it is a
            shape, and it changes when the price does. Watch the downside cross zero. That is the
            whole company: we give you the range, and we will tell you when not to spend.
          </ScrollReveal>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              href="/start"
              className="inline-flex items-center gap-2 rounded-lg bg-brand px-5 py-3 font-semibold text-white transition-colors hover:bg-brand-deep"
            >
              Choose your industry →
            </Link>
            <Link href="/methodology" className="link-underline px-1 py-3 text-sm text-ink/70">
              See how every number is computed
            </Link>
          </div>
        </div>

        {/* Right: the live decision */}
        <div className="rounded-2xl border border-rule bg-surface p-5 shadow-lift sm:p-7">
          {/* Industry selector. The point is that this works for all five. */}
          <div className="flex flex-wrap gap-1.5">
            {(data || []).map((d, i) => (
              <button
                key={d.id}
                onClick={() => { setActive(i); setCostScale(1); }}
                aria-pressed={i === active}
                className={`rounded-md px-2.5 py-1 font-mono text-[0.62rem] uppercase tracking-wide transition ${
                  i === active ? "bg-brand text-white" : "bg-raised text-muted hover:text-ink"
                }`}
              >
                {SHORT[d.id] || d.name}
              </button>
            ))}
          </div>

          {ind && priced ? (
            <>
              <div className="mt-4 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="eyebrow">Should you fund it</div>
                  <div className="mt-0.5 font-display text-base font-bold leading-snug text-ink">
                    {priced.title}
                  </div>
                </div>
                <span className="shrink-0 rounded-full bg-raised px-2 py-0.5 font-mono text-[0.58rem] uppercase tracking-wide text-muted">
                  3-yr NPV
                </span>
              </div>

              <div className="mt-3 min-h-[210px]">
                <DistributionChart
                  expected={priced.npv}
                  p10={priced.npv_p10}
                  p90={priced.npv_p90}
                  threshold={0}
                  height={210}
                />
              </div>

              {/* The lever every operator argues about. */}
              <div className="mt-3">
                <div className="flex items-baseline justify-between">
                  <label htmlFor="hero-cost" className="text-sm font-medium text-ink">
                    What the action costs you
                  </label>
                  <span className="font-mono text-lg font-semibold tabular-nums text-brand">
                    {money(totalCost)}
                  </span>
                </div>
                <input
                  id="hero-cost"
                  type="range"
                  min={0.2}
                  max={2}
                  step={0.05}
                  value={costScale}
                  onChange={(e) => setCostScale(parseFloat(e.target.value))}
                  className="mt-2 w-full accent-brand"
                />
                <div className="mt-1 flex justify-between font-mono text-[0.55rem] text-muted">
                  <span>a fifth of our estimate</span>
                  <span>our estimate</span>
                  <span>twice it</span>
                </div>
              </div>

              <div className="mt-5 grid grid-cols-3 gap-3 border-t border-rule pt-4">
                <Readout label="Downside · P10" value={moneyCompact(priced.npv_p10)} warn={priced.npv_p10 < 0} />
                <Readout label="Expected" value={moneyCompact(priced.npv)} warn={priced.npv < 0} />
                <Readout label="Upside · P90" value={moneyCompact(priced.npv_p90)} />
              </div>
              <p className="mt-3 text-sm text-ink/80 tnum">
                Worth funding in{" "}
                <span className="font-semibold text-brand">{pct(priced.prob_beneficial)}</span> of{" "}
                scenarios, against {money(ind.expected_annual_loss)} of expected annual loss across{" "}
                {ind.domains.length} risk domains.
                {priced.npv < 0 && (
                  <span className="text-muted"> At this price we would tell you not to do it.</span>
                )}
              </p>
            </>
          ) : (
            <div className="mt-4 flex h-[380px] items-center justify-center text-center text-sm text-muted">
              {offline
                ? "Start the backend to see the live models."
                : "Loading the engine…"}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

const SHORT: Record<string, string> = {
  industrial_distribution: "Distribution",
  automotive_manufacturing: "Manufacturing",
  clinical_research: "Clinical",
  property_data: "Data & property",
  wealth_management: "Wealth",
};

function Readout({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div>
      <div className="font-mono text-[0.6rem] uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-0.5 font-mono text-sm font-semibold tabular-nums ${warn ? "text-amber" : "text-ink"}`}>
        {value}
      </div>
    </div>
  );
}

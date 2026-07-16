"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { analyze, type AnalyzeResponse } from "@/lib/api";
import { money, pct } from "@/lib/format";
import { useDebouncedCallback } from "@/lib/useDebouncedCallback";
import { DistributionChart } from "@/components/charts/DistributionChart";
import { DottedWaves } from "@/components/DottedWaves";
import { ScrollFloat, ScrollReveal } from "@/components/ScrollFloat";

/**
 * The signature element. Drag the tariff rate and the outcome distribution moves
 * in real time, every number computed by the validated Python engine (a small,
 * fast run of 2,000 scenarios, debounced), never invented on the client. Watch
 * P10 cross zero: that is the whole thesis, the shape, not a single number.
 */
export function LiveHero() {
  const [tariff, setTariff] = useState(0.25);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [offline, setOffline] = useState(false);
  const reqId = useRef(0);

  const run = (rate: number) => {
    const id = ++reqId.current;
    setRunning(true);
    analyze({ risk_type: "tariff", params: { current_tariff_rate: rate, n_sims: 2000 } })
      .then((r) => {
        if (id === reqId.current) {
          setResult(r);
          setOffline(false);
        }
      })
      .catch(() => setOffline(true))
      .finally(() => id === reqId.current && setRunning(false));
  };

  const debouncedRun = useDebouncedCallback(run, 140);

  useEffect(() => {
    run(0.25);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const o = result?.model_output;
  const beneficial = o?.prob_reroute_beneficial ?? 0;

  return (
    <section className="relative overflow-hidden border-b border-mist bg-surface">
      <DottedWaves corner="tl" className="pointer-events-none absolute -left-10 -top-10 h-[380px] w-[380px]" drift />
      <DottedWaves corner="br" color="#8F0F24" className="pointer-events-none absolute -bottom-16 -right-10 h-[340px] w-[340px]" opacity={0.4} />

      <div className="container-x relative grid items-center gap-12 py-16 lg:grid-cols-[1.05fr_1.25fr] lg:py-24">
        {/* Left: the argument */}
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-crimson" />
            <span className="eyebrow">Enterprise risk, industrial distribution</span>
          </div>
          <div className="mt-5 flex gap-4">
            <span className="mt-1 hidden w-[3px] shrink-0 rounded-full bg-bordeaux sm:block" />
            <ScrollFloat
              as="h1"
              className="font-display text-display-lg font-extrabold"
              segments={[
                { text: "Risk, priced in dollars.", className: "text-ink" },
                { text: "Not “High.” Not a color.", className: "text-bordeaux" },
              ]}
            />
          </div>
          <ScrollReveal as="p" className="mt-6 max-w-md text-lg leading-relaxed text-muted">
            Drag the tariff rate. The answer is not one number, it is a shape. Watch the downside cross
            zero, and the probability of benefit move with it. This is the whole company: we give you the
            range, not a false certainty.
          </ScrollReveal>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              href="/upload"
              className="inline-flex items-center gap-2 rounded-lg bg-bordeaux px-5 py-3 font-semibold text-white transition-colors hover:bg-bordeaux-deep"
            >
              Run a real analysis →
            </Link>
            <Link href="/methodology" className="link-underline px-1 py-3 text-sm text-ink/70">
              See how every number is computed
            </Link>
          </div>
        </div>

        {/* Right: the live distribution */}
        <div className="rounded-2xl border border-mist bg-surface p-5 shadow-lift sm:p-7">
          <div className="flex items-start justify-between gap-3">
            <div className="eyebrow max-w-[70%]">Outcome distribution · 3-yr net savings from rerouting</div>
            <span className="flex shrink-0 items-center gap-1.5 font-mono text-[0.62rem] text-muted">
              <span className={`h-1.5 w-1.5 rounded-full ${running ? "bg-ochre" : "bg-bordeaux"}`} />
              {running ? "computing" : "live"}
            </span>
          </div>

          <div className="mt-3 min-h-[268px]">
            {o ? (
              <DistributionChart
                expected={o.net_savings_pv_expected}
                p10={o.net_savings_pv_p10}
                p90={o.net_savings_pv_p90}
                threshold={0}
                height={268}
              />
            ) : (
              <div className="flex h-[268px] items-center justify-center text-sm text-muted">
                {offline ? "Start the backend to see the live distribution." : "Loading the engine…"}
              </div>
            )}
          </div>

          {/* Slider */}
          <div className="mt-3">
            <div className="flex items-baseline justify-between">
              <label htmlFor="hero-tariff" className="text-sm font-medium text-ink">
                Current tariff rate
              </label>
              <span className="font-mono text-lg font-semibold tabular-nums text-bordeaux">{pct(tariff)}</span>
            </div>
            <input
              id="hero-tariff"
              type="range"
              min={0.05}
              max={0.5}
              step={0.01}
              value={tariff}
              onChange={(e) => {
                const v = parseFloat(e.target.value);
                setTariff(v);
                debouncedRun(v);
              }}
              className="mt-2 w-full accent-bordeaux"
            />
          </div>

          {/* Readouts */}
          <div className="mt-5 grid grid-cols-3 gap-3 border-t border-mist pt-4">
            <Readout label="Downside · P10" value={o ? money(o.net_savings_pv_p10) : "-"} tone={o && o.net_savings_pv_p10 < 0 ? "ochre" : "bordeaux"} />
            <Readout label="Expected" value={o ? money(o.net_savings_pv_expected) : "-"} tone="bordeaux" />
            <Readout label="Upside · P90" value={o ? money(o.net_savings_pv_p90) : "-"} tone="bordeaux" />
          </div>
          <p className="mt-3 text-sm text-ink/80 tnum">
            Rerouting is net-beneficial in{" "}
            <span className="font-semibold text-bordeaux">{o ? pct(beneficial) : "-"}</span> of scenarios.
            {o && o.net_savings_pv_p10 < 0 && (
              <span className="text-muted"> The downside still crosses into loss, that is the risk you would be taking.</span>
            )}
          </p>
        </div>
      </div>
    </section>
  );
}

function Readout({ label, value, tone }: { label: string; value: string; tone: "bordeaux" | "ochre" }) {
  return (
    <div>
      <div className="font-mono text-[0.6rem] uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-0.5 font-mono text-sm font-semibold tabular-nums ${tone === "ochre" ? "text-ochre" : "text-ink"}`}>
        {value}
      </div>
    </div>
  );
}

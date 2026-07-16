"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { analyze, getModels, type AnalyzeResponse, type ModelSpec } from "@/lib/api";
import { byType, money, pct } from "@/lib/format";
import { Badge, Card, Eyebrow } from "@/components/ui";
import { ErrorPanel, LoadingPanel } from "@/components/StatePanels";
import { AssumptionsPanel } from "@/components/AssumptionsPanel";
import { InterpretationPanel } from "@/components/InterpretationPanel";
import { DistributionChart } from "@/components/charts/DistributionChart";
import { LossDistribution } from "@/components/charts/LossDistribution";
import { Trace } from "@/components/Trace";

export default function DomainPage({ params }: { params: { domain: string } }) {
  const { domain } = params;
  const [spec, setSpec] = useState<ModelSpec | null>(null);
  const [values, setValues] = useState<Record<string, any>>({});
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout>>();
  const reqId = useRef(0);

  // Load the model spec (drives the human-labeled inputs) once.
  useEffect(() => {
    getModels()
      .then(({ models }) => {
        const s = models.find((m) => m.key === domain);
        if (!s) return setNotFound(true);
        setSpec(s);
        const init: Record<string, any> = {};
        s.parameters.forEach((p) => (init[p.name] = p.default));
        setValues(init);
      })
      .catch((e) => setError(e.message));
  }, [domain]);

  const run = (vals: Record<string, any>) => {
    const id = ++reqId.current;
    setRunning(true);
    analyze({ risk_type: domain, params: vals })
      .then((r) => id === reqId.current && (setResult(r), setError(null)))
      .catch((e) => id === reqId.current && setError(e.message))
      .finally(() => id === reqId.current && setRunning(false));
  };

  useEffect(() => {
    if (spec && Object.keys(values).length) run(values);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spec]);

  const onChange = (v: Record<string, any>) => {
    setValues(v);
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => run(v), 220);
  };

  const o = result?.model_output;

  const chart = useMemo(() => {
    if (!o) return null;
    if (domain === "tariff")
      return <DistributionChart expected={o.net_savings_pv_expected} p10={o.net_savings_pv_p10} p90={o.net_savings_pv_p90} threshold={0} />;
    if (domain === "price")
      return <DistributionChart expected={o.expected_gross_profit} p10={o.gross_profit_p10} p90={o.gross_profit_p90} threshold={0} />;
    if (o.risk_summary?.quantiles)
      return <LossDistribution quantiles={o.risk_summary.quantiles} p95={o.risk_summary.p95_loss} />;
    return null;
  }, [o, domain]);

  if (notFound)
    return (
      <div className="container-x py-20 text-center">
        <h1 className="font-display text-2xl text-ink">Unknown domain</h1>
        <p className="mt-2 text-muted">No model registered for “{domain}”.</p>
        <Link href="/dashboard" className="link-underline mt-4 inline-block text-bordeaux">← Back to dashboard</Link>
      </div>
    );

  return (
    <div className="container-x py-10">
      <Link href="/dashboard" className="font-mono text-[0.7rem] text-muted hover:text-bordeaux">← Dashboard</Link>
      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl">
          <Eyebrow>{spec?.domain}</Eyebrow>
          <h1 className="mt-2 font-display text-4xl font-bold tracking-tight text-ink">{spec?.name || domain}</h1>
          {spec && <p className="mt-3 text-muted">{spec.method}</p>}
        </div>
        {result && <Trace trace={result.trace} />}
      </div>

      {error && <div className="mt-8"><ErrorPanel error={error} onRetry={() => run(values)} /></div>}
      {!spec && !error && <div className="mt-8"><LoadingPanel title="Loading model" detail="Fetching the model specification." /></div>}

      {spec && (
        <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_1.35fr]">
          {/* Assumptions */}
          <Card className="h-fit p-6">
            <AssumptionsPanel params={spec.parameters} values={values} onChange={onChange} />
          </Card>

          {/* Results */}
          <div className="space-y-6">
            <Card className="p-6">
              <div className="flex items-center justify-between">
                <Eyebrow>Outcome distribution</Eyebrow>
                <span className="flex items-center gap-1.5 font-mono text-[0.62rem] text-muted">
                  <span className={`h-1.5 w-1.5 rounded-full ${running ? "bg-ochre" : "bg-bordeaux"}`} />
                  {running ? "recomputing" : "live"}
                </span>
              </div>
              <div className="mt-3 min-h-[220px]">{chart || (o ? <NoChart /> : <ChartLoading />)}</div>

              {/* Highlighted outputs */}
              {o && (
                <div className="mt-4 grid grid-cols-2 gap-4 border-t border-mist pt-4 sm:grid-cols-4">
                  {spec.outputs.map((out) => {
                    const isTail = out.key.includes("p95") || out.key.includes("p10") || out.key.includes("prob_margin");
                    return (
                      <div key={out.key}>
                        <div className="font-mono text-[0.6rem] uppercase tracking-wide text-muted">{out.label}</div>
                        <div className={`mt-0.5 font-mono text-lg font-semibold tabular-nums ${isTail ? "text-ochre" : "text-ink"}`}>
                          {byType(o[out.key], out.type)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>

            {domain === "supplier_health" && o?.sub_scores && <FlagshipFactors o={o} />}

            {result && <InterpretationPanel text={result.interpretation} />}
          </div>
        </div>
      )}
    </div>
  );
}

/** Flagship detail: the Bayesian distress factors and the probability's credible interval. */
function FlagshipFactors({ o }: { o: Record<string, any> }) {
  const factors = Object.entries(o.sub_scores as Record<string, number>);
  return (
    <Card className="p-6">
      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <Eyebrow>Distress factors</Eyebrow>
          <div className="mt-3 space-y-2.5">
            {factors.map(([k, v]) => (
              <div key={k}>
                <div className="flex justify-between text-xs">
                  <span className="capitalize text-ink/80">{k}</span>
                  <span className="font-mono tabular-nums text-muted">{v.toFixed(2)}</span>
                </div>
                <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-mist">
                  <div className={`h-full rounded-full ${v > 0.6 ? "bg-ochre" : "bg-bordeaux"}`} style={{ width: `${v * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
        <div>
          <Eyebrow>Probability of distress · 12mo</Eyebrow>
          <div className="mt-2 font-display text-4xl font-bold tabular-nums text-bordeaux">
            {pct(o.probability_of_distress, 1)}
          </div>
          <div className="mt-2 font-mono text-xs text-muted tnum">
            Credible interval P10-P90: {pct(o.pd_p10, 1)} - {pct(o.pd_p90, 1)}
          </div>
          <div className="mt-4 rounded-lg bg-paper p-3">
            <div className="flex justify-between text-sm">
              <span className="text-muted">Loss if distress occurs</span>
              <span className="font-mono tabular-nums text-ink">{money(o.loss_given_distress)}</span>
            </div>
            <div className="mt-1.5 flex justify-between text-sm">
              <span className="text-muted">Expected annual loss</span>
              <span className="font-mono tabular-nums text-ink">{money(o.expected_annual_loss)}</span>
            </div>
          </div>
          <Badge tone="bordeaux">Bayesian · Beta-updated posterior</Badge>
        </div>
      </div>
    </Card>
  );
}

function ChartLoading() {
  return <div className="flex h-[220px] items-center justify-center text-sm text-muted">Running scenarios…</div>;
}
function NoChart() {
  return (
    <div className="flex h-[220px] items-center justify-center text-center text-sm text-muted">
      This model reports point tail metrics (VaR / expected shortfall), see the figures below.
    </div>
  );
}

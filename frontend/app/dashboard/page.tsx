"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { assess, assessRobustness, type Assessment, type PricedDecision, type RobustnessResponse } from "@/lib/api";
import { DecisionCard } from "@/components/dashboard/DecisionCard";
import { ExposureWaterfall } from "@/components/dashboard/ExposureWaterfall";
import { money, moneyCompact, pct } from "@/lib/format";
import { useSession } from "@/lib/session";
import { repriceAll, type CostOverride } from "@/lib/reprice";
import { ErrorPanel, LoadingPanel } from "@/components/StatePanels";
import { InterpretationPanel } from "@/components/InterpretationPanel";
import { ExceedanceCurve } from "@/components/charts/ExceedanceCurve";
import { HeadlineBand } from "@/components/dashboard/HeadlineBand";
import { FragilityPanel } from "@/components/dashboard/FragilityPanel";
import { Eyebrow } from "@/components/ui";

export default function DashboardPage() {
  const { industry, answers, ready } = useSession();
  const [data, setData] = useState<Assessment | null>(null);
  const [rob, setRob] = useState<RobustnessResponse | null>(null);
  const [started, setStarted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingRob, setLoadingRob] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [eps, setEps] = useState(0.1);
  // What the reader actually gets. Choosing one HIDES the others: showing every
  // format at once is the information overload this control exists to prevent.
  const [view, setView] = useState<"summary" | "onepager" | "full">("summary");
  // What the operator says each action costs THEM. Sent back on a re-run so an
  // edited assessment is reproducible, not something that lived in one tab.
  const [costs, setCosts] = useState<Record<string, CostOverride>>({});
  const robReq = useRef(0);

  const loadRobustness = useCallback(
    (e: number) => {
      if (!industry) return;
      const id = ++robReq.current;
      setLoadingRob(true);
      assessRobustness({ industry, answers, eps: e })
        .then((r) => {
          if (id !== robReq.current) return;
          setRob(r);
          // sensitivity and the narrative ride along with this deferred call
          setData((prev) => (prev ? { ...prev, sensitivity: (r as any).sensitivity ?? prev.sensitivity, interpretation: (r as any).interpretation ?? prev.interpretation } : prev));
        })
        .catch(() => {})
        .finally(() => id === robReq.current && setLoadingRob(false));
    },
    [industry, answers]
  );

  const run = useCallback(() => {
    if (!industry) return;
    setStarted(true);
    setLoading(true);
    setError(null);
    setRob(null);
    assess({ industry, answers, decision_costs: costs })
      .then((a) => {
        setData(a);
        // The dependence sweep is ~90 simulations, so it loads after the
        // dashboard paints rather than holding it hostage.
        loadRobustness(eps);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [industry, answers, eps, costs, loadRobustness]);

  useEffect(() => {
    if (!ready) return;
    if (typeof window !== "undefined" && new URLSearchParams(window.location.search).get("run") === "1") {
      run();
    }
  }, [ready]); // eslint-disable-line react-hooks/exhaustive-deps

  // Repriced in the browser: NPV is affine in cost, so an edited price is
  // exact rather than approximate, and instant rather than a round trip.
  const decisions = data?.decisions ? repriceAll(data.decisions, costs) : [];

  const onEps = (v: number) => {
    setEps(v);
    if (data) loadRobustness(v);
  };

  if (ready && !industry) {
    return (
      <div className="container-x py-20 text-center">
        <h1 className="font-display text-2xl font-bold text-ink">Pick an industry first</h1>
        <p className="mt-2 text-muted">The models, questions and relationships all depend on it.</p>
        <Link href="/start" className="mt-5 inline-block rounded-lg bg-brand px-5 py-3 font-semibold text-white hover:bg-brand-deep">
          Choose your industry
        </Link>
      </div>
    );
  }

  return (
    <div className="container-x py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Eyebrow>Step 3 of 3 · composite assessment</Eyebrow>
          <h1 className="mt-2 font-display text-4xl font-bold tracking-tight text-ink sm:text-5xl">
            Risk dashboard
          </h1>
        </div>
        {data && (
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex rounded-lg border border-rule bg-surface p-0.5">
              {([
                ["summary", "Executive summary"],
                ["onepager", "One-pager"],
                ["full", "Full analysis"],
              ] as const).map(([v, label]) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  aria-pressed={view === v}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                    view === v ? "bg-brand text-white" : "text-muted hover:text-ink"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <Link href="/intake" className="link-underline text-sm text-muted">Adjust answers</Link>
            <button
              onClick={run}
              className="rounded-lg border border-rule px-3.5 py-1.5 text-sm font-medium text-ink transition-colors hover:border-brand hover:text-brand"
            >
              Re-run
            </button>
          </div>
        )}
      </div>

      {!started && !data && (
        <div className="mt-8 rounded-2xl border border-rule bg-surface p-10 shadow-card">
          <div className="max-w-xl">
            <h2 className="font-display text-2xl font-bold text-ink">Run the composite assessment</h2>
            <p className="mt-3 text-muted">
              This runs every model for your industry plus the cross-domain correlation, at 50,000
              scenarios each. Nothing runs until you start it.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <button onClick={run} className="rounded-lg bg-brand px-5 py-3 font-semibold text-white hover:bg-brand-deep">
                Run assessment →
              </button>
              <Link href="/intake" className="rounded-lg border border-rule px-5 py-3 font-medium text-ink hover:border-brand hover:text-brand">
                Review my answers
              </Link>
            </div>
          </div>
        </div>
      )}

      {loading && !data && (
        <div className="mt-8">
          <LoadingPanel title="Running 50,000 scenarios" detail="Sampling each domain, then correlating the tails with a t-copula." />
        </div>
      )}
      {error && <div className="mt-8"><ErrorPanel error={error} onRetry={run} /></div>}

      {data && (
        <div className={`mt-8 space-y-8 ${loading ? "opacity-60 transition-opacity" : ""}`}>
          {view === "summary" && <ExecutiveSummary a={data} r={rob} decisions={decisions} />}

          {/* THE LEAD: what to actually do, priced. */}
          {view !== "summary" && data.decisions?.length > 0 && (
            <section>
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <Eyebrow>Decisions on your desk</Eyebrow>
                  <h2 className="mt-1 font-display text-2xl font-bold text-ink sm:text-3xl">
                    What to fund, and what to leave alone
                  </h2>
                </div>
                <p className="max-w-sm text-sm text-muted">
                  Each option re-run through the same 50,000 scenarios with it in place, paired
                  against the same years without it.
                </p>
              </div>

              <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {decisions.map((d) => (
                  <DecisionCard
                    key={d.id}
                    d={d}
                    edited={!!costs[d.id]}
                    onCostChange={(patch) =>
                      setCosts((s) => ({ ...s, [d.id]: { ...s[d.id], ...patch } }))
                    }
                  />
                ))}
              </div>

              <div className="mt-6 rounded-2xl border border-rule bg-surface p-6 shadow-card">
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <Eyebrow>If you act</Eyebrow>
                    <h3 className="mt-1 font-display text-lg font-bold text-ink">
                      Expected annual loss, before and after
                    </h3>
                  </div>
                  <span className="font-mono text-[0.62rem] text-muted">
                    only actions that pay for themselves are subtracted
                  </span>
                </div>
                <div className="mt-5">
                  <ExposureWaterfall baseline={data.expected_annual_loss} decisions={decisions} />
                </div>
              </div>
            </section>
          )}

          {/* Supporting evidence below the decisions. */}
          {view === "full" && <HeadlineBand a={data} r={rob} loadingRobustness={loadingRob} />}

          {view === "full" && <div className="grid gap-8 lg:grid-cols-[1.05fr_0.95fr]">
            <div className="rounded-2xl border border-rule bg-surface p-6 shadow-card">
              <Eyebrow>Loss exceedance</Eyebrow>
              <h2 className="mt-1 font-display text-xl font-bold text-ink">How bad it gets, by percentile</h2>
              <div className="mt-4">
                <ExceedanceCurve
                  correlated={data.exceedance_curve}
                  independent={data.exceedance_curve_independent}
                />
              </div>
              <p className="mt-2 flex flex-wrap items-center gap-4 font-mono text-[0.66rem] text-muted">
                <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-brand" />correlated</span>
                <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 border-t border-dashed border-muted" />if independent</span>
              </p>
            </div>

            <FragilityPanel r={rob} loading={loadingRob} eps={eps} onEps={onEps} />
          </div>}

          {view === "full" && <div className="grid gap-8 lg:grid-cols-2">
            {data.sensitivity?.length ? <Tornado rows={data.sensitivity} /> : <div className="rounded-2xl border border-rule bg-surface p-6 shadow-card"><Eyebrow>Sensitivity</Eyebrow><p className="mt-3 text-sm text-muted">Measuring which assumption moves the answer...</p></div>}
            <Contributions data={data} />
          </div>}

          {view !== "summary" && <div className="grid gap-8 lg:grid-cols-2">
            <div>
              <Eyebrow>The read</Eyebrow>
              <h2 className="mt-1 font-display text-xl font-bold text-ink">What this means</h2>
              <div className="mt-4">{data.interpretation ? <InterpretationPanel text={data.interpretation} /> : <div className="rounded-xl border border-rule bg-surface p-5 text-sm text-muted">Writing the read...</div>}</div>
            </div>
          </div>}

          {view === "full" && <ModelConfiguration data={data} />}
        </div>
      )}
    </div>
  );
}

/** Executive summary: one call, one number, one caveat. Nothing else. */
function ExecutiveSummary({
  a, r, decisions,
}: {
  a: Assessment; r: RobustnessResponse | null; decisions: PricedDecision[];
}) {
  const top = decisions[0];
  const worth = decisions.filter((d) => d.npv > 0);
  const P = Object.fromEntries(a.exceedance_curve.map((e) => [e.percentile, e.loss]));
  return (
    <div className="rounded-2xl border border-rule bg-surface p-8 shadow-card sm:p-10">
      <Eyebrow>{a.industry_name} · executive summary</Eyebrow>

      {top && (
        <p className="thesis mt-4 max-w-3xl text-2xl leading-snug text-ink sm:text-3xl">
          {worth.length > 0 ? (
            <>
              <span className="text-brand">{top.title}</span>. It returns{" "}
              <span className="text-emerald">{money(top.npv)}</span> over three years and is worth
              doing in {pct(top.prob_beneficial)} of scenarios.
            </>
          ) : (
            <>
              None of the {decisions.length} actions we priced pays for itself at current
              estimates. Your exposure is cheaper to carry than to remove.
            </>
          )}
        </p>
      )}

      <div className="mt-8 grid gap-6 border-t border-rule pt-6 sm:grid-cols-3">
        <div>
          <div className="eyebrow">Expected annual loss</div>
          <div className="mt-1 font-display text-3xl font-bold tabular-nums text-ink">
            {money(a.expected_annual_loss)}
          </div>
          {a.expected_annual_loss_pct_revenue && (
            <div className="mt-0.5 font-mono text-[0.66rem] text-muted">
              {pct(a.expected_annual_loss_pct_revenue, 2)} of revenue
            </div>
          )}
        </div>
        <div>
          <div className="eyebrow">Plan against · P99</div>
          <div className="mt-1 font-display text-3xl font-bold tabular-nums text-brand">
            {money(P[99])}
          </div>
          <div className="mt-0.5 font-mono text-[0.66rem] text-muted">
            {r ? `range ${moneyCompact(r.robustness.p99_low)} to ${moneyCompact(r.robustness.p99_high)}` : "measuring the range..."}
          </div>
        </div>
        <div>
          <div className="eyebrow">Actions worth funding</div>
          <div className="mt-1 font-display text-3xl font-bold tabular-nums text-ink">
            {worth.length} of {decisions.length}
          </div>
          <div className="mt-0.5 font-mono text-[0.66rem] text-muted">
            {money(worth.reduce((s, d) => s + d.npv, 0))} combined NPV
          </div>
        </div>
      </div>

      <p className="mt-6 border-t border-rule pt-4 text-xs leading-relaxed text-muted">
        Every figure is a seeded simulation over {a.n_sims.toLocaleString("en-US")} scenarios and
        carries a range. Parameters are starting estimates you can edit. Switch to One-pager or Full
        analysis above for the workings.
      </p>
    </div>
  );
}

function Tornado({ rows }: { rows: Assessment["sensitivity"] }) {
  const top = rows.slice(0, 8);
  const max = top[0]?.impact || 1;
  return (
    <div className="rounded-2xl border border-rule bg-surface p-6 shadow-card">
      <Eyebrow>Sensitivity</Eyebrow>
      <h2 className="mt-1 font-display text-xl font-bold text-ink">Which assumption moves the answer</h2>
      <p className="mt-2 text-sm text-muted">
        Each parameter shifted 25% in both directions. Longer bar, more your answer depends on that
        judgment being right.
      </p>
      <div className="mt-5 space-y-2.5">
        {top.map((r) => (
          <div key={`${r.engine}-${r.parameter}`}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="truncate text-ink/85">{r.parameter_label}</span>
              <span className="shrink-0 font-mono text-xs tabular-nums text-muted">{moneyCompact(r.impact)}</span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-rule">
              <div className="h-full rounded-full bg-brand" style={{ width: `${Math.max(3, (r.impact / max) * 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
      <p className="mt-4 border-t border-rule pt-3 font-mono text-[0.62rem] text-muted">
        Movement in portfolio P95, USD
      </p>
    </div>
  );
}

function Contributions({ data }: { data: Assessment }) {
  return (
    <div className="rounded-2xl border border-rule bg-surface p-6 shadow-card">
      <Eyebrow>By domain</Eyebrow>
      <h2 className="mt-1 font-display text-xl font-bold text-ink">Who owns the tail</h2>
      <p className="mt-2 text-sm text-muted">
        Share of a typical year against share of the P95 tail. A domain that grows between the two is
        one that shows up precisely when things are already going badly.
      </p>
      <div className="mt-5 space-y-3">
        {data.domain_contributions.map((d) => {
          const grew = d.tail_share > d.base_share;
          return (
            <div key={d.domain}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <Link href={`/analyze/${d.domain}`} className="truncate text-ink/85 hover:text-brand">
                  {d.label}
                </Link>
                <span className="shrink-0 font-mono text-xs tabular-nums text-muted">
                  {pct(d.base_share)} <span className="text-muted/60">→</span>{" "}
                  <span className={grew ? "text-amber" : "text-ink"}>{pct(d.tail_share)}</span>
                </span>
              </div>
              <div className="mt-1 flex gap-1">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-rule">
                  <div className="h-full rounded-full bg-muted/50" style={{ width: `${d.base_share * 100}%` }} />
                </div>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-rule">
                  <div className={`h-full rounded-full ${grew ? "bg-amber" : "bg-brand"}`} style={{ width: `${d.tail_share * 100}%` }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-4 border-t border-rule pt-3 font-mono text-[0.62rem] text-muted">
        left: share of expected loss · right: share of the P95 tail
      </p>
    </div>
  );
}

function ModelConfiguration({ data }: { data: Assessment }) {
  const [copied, setCopied] = useState(false);
  const cfg = {
    model: data.model,
    version: data.version,
    seed: data.seed,
    n_sims: data.n_sims,
    method: data.method,
    copula: data.assumptions.copula,
    correlation_matrix: data.assumptions.correlation_matrix,
    domains: data.assumptions.domains,
    intake_adjustments: data.intake_adjustments,
  };
  const copy = () => {
    navigator.clipboard?.writeText(JSON.stringify(cfg, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };
  const m = data.assumptions.correlation_matrix;

  return (
    <div className="rounded-2xl border border-rule bg-surface p-6 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="eyebrow">Model configuration</div>
          <h2 className="mt-1 font-display text-xl font-bold text-ink">Everything needed to reproduce this run</h2>
        </div>
        <button
          onClick={copy}
          className="rounded-lg border border-rule px-3 py-1.5 font-mono text-xs text-muted transition-colors hover:border-brand hover:text-brand"
        >
          {copied ? "copied" : "copy config"}
        </button>
      </div>

      <div className="mt-5 grid gap-6 lg:grid-cols-[1fr_1fr]">
        <pre className="overflow-x-auto rounded-xl border border-rule bg-raised p-4 font-mono text-xs leading-relaxed">
          {[
            ["model", data.model],
            ["version", data.version],
            ["seed", String(data.seed)],
            ["n_sims", data.n_sims.toLocaleString("en-US")],
            ["copula", `${data.assumptions.copula.family}, df=${data.assumptions.copula.df}`],
            ["applied_to", data.assumptions.copula.applied_to],
            ["matrix_repaired", String(m.repaired)],
          ].map(([k, v]) => (
            <div key={k}>
              <span className="text-muted">{k}</span>
              <span className="text-muted/50">: </span>
              <span className="text-brand">{v}</span>
            </div>
          ))}
        </pre>

        <div>
          <div className="eyebrow">Correlation matrix</div>
          <div className="mt-2 overflow-x-auto">
            <table className="border-separate border-spacing-0.5">
              <tbody>
                {m.matrix.map((row, i) => (
                  <tr key={i}>
                    <td className="pr-2 text-right font-mono text-[0.58rem] text-muted">
                      {m.labels[i]?.split(" ")[0]}
                    </td>
                    {row.map((v, j) => (
                      <td key={j}>
                        <div
                          title={`${m.labels[i]} x ${m.labels[j]}: ${v.toFixed(2)}`}
                          className="flex h-7 w-9 items-center justify-center rounded font-mono text-[0.6rem] tabular-nums"
                          style={{
                            background:
                              i === j
                                ? "rgb(var(--brand-deep))"
                                : `rgb(var(--brand) / ${0.06 + Math.max(0, v) * 0.6})`,
                            color: i === j || v > 0.55 ? "#fff" : "rgb(var(--ink))",
                          }}
                        >
                          {v.toFixed(2)}
                        </div>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <p className="mt-5 border-t border-rule pt-4 text-xs leading-relaxed text-muted">
        {data.assumptions.parameter_basis}
      </p>
    </div>
  );
}

"use client";
import { useEffect, useState } from "react";
import { getModels, type ModelsResponse } from "@/lib/api";
import { Card, Eyebrow } from "@/components/ui";
import { ErrorPanel, LoadingPanel } from "@/components/StatePanels";

export default function MethodologyPage() {
  const [m, setM] = useState<ModelsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getModels().then(setM).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="container-x py-12">
      <div className="max-w-3xl">
        <Eyebrow>Glass box</Eyebrow>
        <h1 className="mt-2 font-display text-4xl font-bold tracking-tight text-ink sm:text-5xl">Methodology</h1>
        <p className="mt-4 text-muted">
          Every number this product shows comes from one of the validated, seeded functions below. The
          AI chooses which to run and explains the output. It never writes the math and never
          introduces a figure the models did not produce. This page is generated from the running
          registry, so it cannot drift from the code.
        </p>
      </div>

      {error && <div className="mt-8"><ErrorPanel error={error} /></div>}
      {!m && !error && <div className="mt-8"><LoadingPanel title="Loading the registry" detail="Reading every engine's specification." /></div>}

      {m && (
        <div className="mt-12 space-y-12">
          {/* Second-order uncertainty: the differentiator, made legible */}
          <section className="rounded-2xl border border-brand/25 bg-brand/[0.04] p-6 sm:p-8">
            <Eyebrow>The part that is ours</Eyebrow>
            <h2 className="mt-2 font-display text-2xl font-bold text-ink">Second-order uncertainty</h2>
            <p className="thesis mt-4 max-w-3xl text-[1.05rem] leading-relaxed text-ink">
              Ordinary risk modelling measures uncertainty <em>within</em> a model: given these
              assumptions, how bad can a year get? We also measure uncertainty <em>about</em> the
              model: if the assumed relationships between your risks were somewhat different, as they
              honestly might be, how much would the answer move?
            </p>
            <p className="mt-4 max-w-3xl text-sm leading-relaxed text-muted">
              We do this because the correlation matrix is the weakest input in every product in this
              category. It is expert judgment with no loss history behind it, ours included. Rather
              than report a confident tail figure as though the matrix were known, we sweep a
              neighbourhood of plausible dependence structures and report the envelope, plus a ranking
              of which single relationship your answer is most sensitive to. That turns our weakest
              input into a usable output, and unlike a claim about accuracy it is provable, because it
              is a computation you can watch.
            </p>
            <p className="mt-4 max-w-3xl text-sm leading-relaxed text-muted">
              A note on what we do not claim: accuracy requires validation against realized losses over
              years, which no one in this segment has yet. We do not assert it. Robustness we can show
              you today.
            </p>
          </section>

          {/* How the engine works */}
          <section>
            <h2 className="font-display text-2xl font-bold text-ink">How a number gets made</h2>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {[
                ["Frequency", "How often a loss event happens, drawn from a PERT distribution over a minimum, most likely and maximum estimate."],
                ["Magnitude", "What one event costs, drawn from a lognormal calibrated to a typical cost and a 90th-percentile bad case. Solved numerically, because the analytic shortcut miscalibrates the tail and the tail is the point."],
                ["Dependence", `A t-copula with ${m.settings.copula.df} degrees of freedom, applied to ${m.settings.copula.applied_to} rather than frequency: a macro shock makes every loss worse at once, it does not make event counts move together. A Gaussian copula would make extreme events asymptotically independent no matter the correlation, which is the assumption that mispriced CDOs in 2008.`],
                ["Aggregation", `Every domain summed per scenario, ${m.settings.n_sims.toLocaleString("en-US")} scenarios, seed ${m.settings.seed}. The same inputs always produce the same numbers.`],
              ].map(([h, b]) => (
                <Card key={h} className="p-5">
                  <div className="font-display text-base font-bold text-ink">{h}</div>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{b}</p>
                </Card>
              ))}
            </div>
            <p className="mt-4 max-w-3xl text-sm leading-relaxed text-muted">
              The headline comparison is your correlated portfolio against the same portfolio with
              identical marginals modelled as independent. It is deliberately not the sum of each
              domain&apos;s standalone percentile, which is a different quantity and would flatter the
              result. Note also that correlation barely moves expected loss at all. Expectation is
              linear; dependence changes the tail, not the average.
            </p>
          </section>

          {/* Engines */}
          <section>
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="font-display text-2xl font-bold text-ink">The engines</h2>
              <span className="font-mono text-[0.66rem] text-muted tnum">{m.engines.length} registered</span>
            </div>
            <p className="mt-2 max-w-3xl text-sm text-muted">
              Industry-agnostic by design. An industry pack supplies the label, the parameters and the
              correlation structure; the engine itself never knows which industry it is running for.
            </p>
            <div className="mt-6 space-y-4">
              {m.engines.map((e) => (
                <Card key={e.key} className="p-6">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="max-w-3xl">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-display text-lg font-bold text-ink">{e.name}</h3>
                        <span className="rounded-full border border-rule bg-raised px-2 py-0.5 font-mono text-[0.62rem] uppercase tracking-wide text-muted">
                          {e.domain}
                        </span>
                      </div>
                      <p className="mt-2 text-sm text-ink/80">{e.description}</p>
                      <p className="mt-2 text-sm leading-relaxed text-muted">{e.method}</p>
                    </div>
                    <div className="flex flex-col items-end gap-0.5 font-mono text-[0.64rem] text-muted tnum">
                      <span className="text-ink">v{e.version}</span>
                      <span>{e.key}</span>
                    </div>
                  </div>
                  <p className="mt-4 border-t border-rule pt-3 text-xs text-muted">{e.basis}</p>
                </Card>
              ))}
            </div>
          </section>

          {/* Modulation rules */}
          <section>
            <h2 className="font-display text-2xl font-bold text-ink">How your answers change the model</h2>
            <p className="mt-2 max-w-3xl text-sm text-muted">
              Every intake question maps to one of these published rules. Leaving a question at its
              default leaves the parameter exactly as calibrated, so nothing moves behind your back.
            </p>
            <div className="mt-5 overflow-x-auto">
              <table className="w-full min-w-[560px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-rule">
                    <th className="py-2 font-mono text-[0.64rem] uppercase tracking-wide text-muted">Rule</th>
                    <th className="py-2 font-mono text-[0.64rem] uppercase tracking-wide text-muted">Effect</th>
                  </tr>
                </thead>
                <tbody>
                  {m.modulation_rules.map((r) => (
                    <tr key={r.rule} className="border-b border-rule/60">
                      <td className="py-2 pr-4 align-top font-mono text-xs text-brand">{r.rule}</td>
                      <td className="py-2 text-ink/80">{r.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Decision models */}
          {m.decision_models.length > 0 && (
            <section>
              <h2 className="font-display text-2xl font-bold text-ink">Decision models</h2>
              <p className="mt-2 max-w-3xl text-sm text-muted">
                These answer a different question from the exposure engines. An engine prices what a
                risk costs you per year; these evaluate a specific decision.
              </p>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                {m.decision_models.map((d: any) => (
                  <Card key={d.key} className="p-5">
                    <div className="flex items-baseline justify-between gap-2">
                      <div className="font-display text-base font-bold text-ink">{d.name}</div>
                      <span className="font-mono text-[0.62rem] text-muted">v{d.version}</span>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-muted">{d.method}</p>
                  </Card>
                ))}
              </div>
            </section>
          )}

          <section className="rounded-2xl border border-rule bg-raised p-6">
            <Eyebrow>On the parameters</Eyebrow>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-ink/85">{m.parameter_basis}</p>
          </section>
        </div>
      )}
    </div>
  );
}

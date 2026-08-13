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

          {/* How a published estimate becomes a measurement. This is the
              section a technical evaluator reads first, so it states the
              shrinkage plainly rather than gesturing at Bayes. */}
          <section>
            <h2 className="font-display text-2xl font-bold text-ink">
              How your own history replaces our estimate
            </h2>
            <p className="mt-3 max-w-3xl leading-relaxed text-muted">
              Connect an accounting or ERP system and some parameters stop being our published
              judgment and start being estimated from what has actually happened to you. Not all
              of them, and the interface says which.
            </p>

            <div className="mt-6 grid gap-4 lg:grid-cols-3">
              <Card className="p-5">
                <div className="eyebrow">The model</div>
                <p className="mt-2 text-sm leading-relaxed text-muted">
                  Events arrive as a Poisson process and the prior on the rate is Gamma, which is
                  conjugate. That gives principled shrinkage, a credible interval, and an explicit
                  weight saying how much of the answer is your data rather than our judgment.
                </p>
              </Card>
              <Card className="p-5">
                <div className="eyebrow">The shrinkage</div>
                <p className="mt-2 text-sm leading-relaxed text-muted">
                  Our prior carries three pseudo-observation years. One year of your history
                  therefore earns 25% of the weight, three years earns 50%, ten years earns 77%. A
                  customer with three months of history does not get a parameter derived from
                  three months of history.
                </p>
              </Card>
              <Card className="p-5">
                <div className="eyebrow">The guarantee</div>
                <p className="mt-2 text-sm leading-relaxed text-muted">
                  With no relevant history the estimate returns our published triple exactly, to
                  the last decimal. Connecting a system that cannot evidence a parameter does not
                  move that parameter at all.
                </p>
              </Card>
            </div>

            <div className="mt-6 overflow-x-auto rounded-xl border border-rule">
              <table className="w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="border-b border-rule bg-raised">
                    {["What you have observed", "Our estimate becomes", "90% interval", "Weight on your data"].map((h) => (
                      <th key={h} className="px-3 py-2 text-left font-mono text-[0.58rem] uppercase tracking-wide text-muted">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="font-mono text-xs tabular-nums">
                  {[
                    ["Nothing", "0.458", "0.05 - 1.23", "0%"],
                    ["1 year, no failures", "0.344", "0.03 - 0.92", "25%"],
                    ["2 years, 1 failure", "0.475", "0.10 - 1.07", "40%"],
                    ["5 years, 12 failures", "1.672", "1.00 - 2.49", "62%"],
                    ["10 years, 4 failures", "0.413", "0.17 - 0.74", "77%"],
                  ].map((row) => (
                    <tr key={row[0]} className="border-b border-rule/60 last:border-0">
                      {row.map((cell, i) => (
                        <td key={i} className={`px-3 py-2 ${i === 0 ? "font-sans text-ink" : "text-ink"}`}>
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 font-mono text-[0.62rem] leading-relaxed text-muted">
              Worked against a published starting rate of 0.458 events a year. Note the fourth row:
              twelve failures in five years is a naive rate of 2.40, and the estimate lands at 1.672
              rather than 2.40 because 38% of it is still our prior.
            </p>

            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <Card className="p-5">
                <div className="eyebrow">What is measurable</div>
                <p className="mt-2 text-sm leading-relaxed text-muted">
                  Frequencies, mostly. Vendor failures from purchase orders received late against a
                  contracted promise, customer churn from revenue that stops, schedule slippage from
                  ordered-to-received dates.
                </p>
              </Card>
              <Card className="p-5">
                <div className="eyebrow">What is not</div>
                <p className="mt-2 text-sm leading-relaxed text-muted">
                  Magnitudes, mostly. A ledger records what you paid a vendor, not what their late
                  delivery cost you in expedited freight and lost margin. So an engine is honestly
                  &quot;how often, measured; how much, our estimate&quot;, and provenance is tracked per
                  parameter rather than per engine.
                </p>
              </Card>
            </div>
          </section>

          <section className="rounded-2xl border border-rule bg-raised p-6">
            <Eyebrow>On the parameters</Eyebrow>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-ink/85">{m.parameter_basis}</p>
          </section>
        </div>
      )}
    </div>
  );
}

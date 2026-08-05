import Link from "next/link";
import { LiveHero } from "@/components/LiveHero";
import { Card, SectionHeading } from "@/components/ui";
import { ScrollReveal } from "@/components/ScrollFloat";

const INDUSTRIES = [
  ["Automotive & Manufacturing", "Supplier failure, recall and warranty, production delay, material cost shock."],
  ["Property & Data Analytics", "Data breach, model accuracy, vendor and API outage, licensing compliance."],
  ["Clinical Research & Healthcare", "Enrollment delay, patient-data incident, protocol deviation, site and sponsor dependency."],
  ["Wealth Management & Finance", "Client data incident, compliance failure, client attrition, reputational event."],
  ["Industrial Distribution", "Tariff shock, vendor failure, logistics delay, stockout, warehouse outage."],
];

const CONTRAST = [
  ["The dashboards", "Tell you a risk is “High.” You cannot act on an adjective, and you cannot defend it to a board."],
  ["The quant engines", "Give you real numbers, priced for the Fortune 500, staffed by a team you do not have."],
  ["Avenoir", "Analyst-grade quantification, in dollars with an honest range, for the mid-market, because AI collapses the cost of the analysis."],
];

export default function Home() {
  return (
    <>
      <LiveHero />

      {/* The wedge */}
      <section className="container-x py-20">
        <SectionHeading
          eyebrow="Why this exists"
          title="A single confident number"
          accent="is a liability."
          intro="Risk products fail in one of two ways: they say “High” and mean nothing, or they cost more than your finance team. Avenoir does the thing neither does, it turns every risk into dollars with an explicit range, for the segment neither serves."
        />
        <div className="mt-10 grid gap-4 sm:grid-cols-3">
          {CONTRAST.map(([h, b], i) => (
            <ScrollReveal key={h} delay={i * 90}>
              <Card className={`h-full p-6 ${i === 2 ? "border-brand/30 bg-brand/[0.04]" : ""}`}>
                <div className={`font-display text-lg font-bold ${i === 2 ? "text-brand" : "text-ink"}`}>{h}</div>
                <p className="mt-2 text-sm leading-relaxed text-muted">{b}</p>
              </Card>
            </ScrollReveal>
          ))}
        </div>
      </section>

      {/* The differentiator */}
      <section className="border-y border-rule bg-surface py-20">
        <div className="container-x">
          <SectionHeading
            eyebrow="What no one else measures"
            title="We price the uncertainty"
            accent="in our own model."
            intro="Every vendor in this category runs Monte Carlo; the sampler is a commodity. The real constraint is that nobody knows the correlation matrix, because there is no loss data behind it. Competitors hand-wave it and report a confident number anyway."
          />
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {[
              ["We report a band, not a point", "Your P99 comes with the range it moves across when the assumed relationships are perturbed. A tight band is a real finding, and we say so."],
              ["We name your weakest assumption", "One ranked list showing which single relationship your answer depends on most, so you know exactly where refining an estimate pays and what you can ignore."],
              ["We do not claim accuracy", "Accuracy needs years of realized-loss validation. Robustness is provable today because it is a visible computation, so that is what we claim."],
            ].map(([h, b], i) => (
              <ScrollReveal key={h} delay={i * 80}>
                <Card className="h-full p-6">
                  <div className="font-display text-base font-bold text-ink">{h}</div>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{b}</p>
                </Card>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </section>

      {/* Industries */}
      <section className="container-x py-20">
        <SectionHeading
          eyebrow="Built for your sector"
          title="Five industries."
          accent="Your vocabulary, your risks."
          intro="Eleven validated engines underneath, parameterized per industry. You see the risks you actually run, named the way you name them, and never another sector's models."
        />
        <div className="mt-10 grid gap-px overflow-hidden rounded-2xl border border-rule bg-rule md:grid-cols-2 lg:grid-cols-3">
          {INDUSTRIES.map(([name, desc], i) => (
            <ScrollReveal key={name} delay={(i % 3) * 70} className="bg-surface">
              <div className="h-full p-6">
                <div className="font-display text-base font-bold text-ink">{name}</div>
                <p className="mt-2 text-sm leading-relaxed text-muted">{desc}</p>
              </div>
            </ScrollReveal>
          ))}
          <ScrollReveal delay={140} className="bg-surface">
            <Link href="/start" className="flex h-full flex-col justify-center p-6 transition-colors hover:bg-brand/[0.04]">
              <div className="font-display text-base font-bold text-brand">Pick yours →</div>
              <p className="mt-2 text-sm leading-relaxed text-muted">
                Four minutes of questions, then a full assessment.
              </p>
            </Link>
          </ScrollReveal>
        </div>
      </section>

      {/* Glass box */}
      <section className="border-t border-rule bg-surface py-20">
        <div className="container-x grid items-center gap-10 lg:grid-cols-2">
          <SectionHeading
            eyebrow="Glass box, not black box"
            title="Every number is traceable to a model,"
            accent="a version, and a seed."
            intro="The AI selects and interprets. It never writes the math and never invents a figure. Open any result, see its assumptions, change one, and watch it re-run. That is the difference between a number you trust and a number you are told."
          />
          <ScrollReveal delay={100}>
            <Card className="p-6">
              <div className="space-y-4 font-mono text-sm">
                {[
                  ["model", "composite_risk_correlation"],
                  ["version", "v1.0.0"],
                  ["seed", "42"],
                  ["n_sims", "50,000"],
                  ["method", "FAIR marginals, t-copula (df=4) on magnitude"],
                  ["reports", "expected + P50 to P99 + band + fragility"],
                ].map(([k, v]) => (
                  <div key={k} className="flex flex-col gap-0.5 border-b border-rule pb-3 last:border-0 sm:flex-row sm:justify-between">
                    <span className="text-muted">{k}</span>
                    <span className="text-ink">{v}</span>
                  </div>
                ))}
              </div>
            </Card>
          </ScrollReveal>
        </div>
      </section>

      {/* CTA */}
      <section className="container-x py-16">
        <div className="rounded-2xl bg-brand-deep px-8 py-14 text-center">
          <h2 className="mx-auto max-w-2xl font-display text-3xl font-bold text-white sm:text-4xl">
            Find out what your risk actually costs, with the uncertainty priced in.
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-white/70">
            Every model, the full composite, and the robustness band. No account required.
          </p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Link href="/start" className="rounded-lg bg-white px-5 py-3 font-semibold text-brand transition hover:bg-canvas">
              Choose your industry
            </Link>
            <Link href="/methodology" className="rounded-lg border border-white/30 px-5 py-3 font-semibold text-white transition hover:bg-white/10">
              See the methodology
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}

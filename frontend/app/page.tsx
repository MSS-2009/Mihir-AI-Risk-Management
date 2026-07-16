import Link from "next/link";
import { LiveHero } from "@/components/LiveHero";
import { Card, SectionHeading } from "@/components/ui";
import { DottedWaves } from "@/components/DottedWaves";
import { ScrollReveal } from "@/components/ScrollFloat";

const DOMAINS = [
  ["Supplier financial health", "Bayesian probability a key supplier hits distress, and the dollars exposed."],
  ["Country & geopolitical", "Disruption probability on concentrated sourcing, priced as annual loss."],
  ["Delivery reliability", "Lead-time shocks against inventory cover, the cost of running short."],
  ["Price & demand volatility", "Correlated price and demand swings against your margin floor."],
  ["Cyber loss exposure", "FAIR-style frequency times magnitude, with the tail a breach actually costs."],
  ["Composite correlation", "How much worse your risks are together than apart, the number no one else gives you."],
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
              <Card className={`h-full p-6 ${i === 2 ? "border-bordeaux/30 bg-bordeaux/[0.03]" : ""}`}>
                <div className={`font-display text-lg font-bold ${i === 2 ? "text-bordeaux" : "text-ink"}`}>{h}</div>
                <p className="mt-2 text-sm leading-relaxed text-muted">{b}</p>
              </Card>
            </ScrollReveal>
          ))}
        </div>
      </section>

      {/* Domains */}
      <section className="relative overflow-hidden border-y border-mist bg-surface py-20">
        <DottedWaves corner="tr" className="pointer-events-none absolute -right-12 -top-10 h-72 w-72" opacity={0.35} />
        <div className="container-x relative">
          <SectionHeading
            eyebrow="What we model"
            title="Eight validated models."
            accent="One correlated picture."
            intro="Each domain is a seeded, deterministic simulation, same inputs, same numbers, every time. The composite is the payoff: risks correlate, so the real tail is worse than the sum of the parts."
          />
          <div className="mt-10 grid gap-px overflow-hidden rounded-2xl border border-mist bg-mist sm:grid-cols-2 lg:grid-cols-3">
            {DOMAINS.map(([name, desc], i) => (
              <ScrollReveal key={name} delay={(i % 3) * 70} className="bg-surface">
                <div className="h-full p-6">
                  <div className="font-display text-base font-bold text-ink">{name}</div>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{desc}</p>
                </div>
              </ScrollReveal>
            ))}
          </div>
          <div className="mt-8">
            <Link href="/methodology" className="link-underline text-sm font-semibold text-bordeaux">
              Read the methodology, every model, method, and assumption →
            </Link>
          </div>
        </div>
      </section>

      {/* Glass box */}
      <section className="container-x py-20">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <SectionHeading
            eyebrow="Glass box, not black box"
            title="Every number is traceable to a model,"
            accent="a version, and a seed."
            intro="The AI selects and interprets. It never writes the math and never invents a figure. You can open any result, see its assumptions, change one, and watch it re-run. That is the difference between a number you trust and a number you are told."
          />
          <ScrollReveal delay={100}>
            <Card className="p-6">
              <div className="space-y-4 font-mono text-sm">
                {[
                  ["model", "supplier_financial_health_bayesian"],
                  ["version", "v1.0.0"],
                  ["seed", "42"],
                  ["method", "Beta-updated distress probability, loss distribution"],
                  ["output", "expected + P10/P90 + P95 tail + assumptions"],
                ].map(([k, v]) => (
                  <div key={k} className="flex flex-col gap-0.5 border-b border-mist pb-3 last:border-0 sm:flex-row sm:justify-between">
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
      <section className="container-x pb-8">
        <div className="relative overflow-hidden rounded-2xl bg-bordeaux-deep px-8 py-14 text-center">
          <DottedWaves corner="tl" color="#ffffff" className="pointer-events-none absolute -left-10 -top-10 h-64 w-64" opacity={0.18} />
          <DottedWaves corner="br" color="#ffffff" className="pointer-events-none absolute -bottom-10 -right-10 h-64 w-64" opacity={0.18} />
          <h2 className="relative mx-auto max-w-2xl font-display text-3xl font-bold text-white sm:text-4xl">
            Upload your trade documents. Get a defensible risk assessment in dollars.
          </h2>
          <p className="relative mx-auto mt-3 max-w-xl text-white/70">
            Free tier runs every model and the full composite. No account required.
          </p>
          <div className="relative mt-7 flex flex-wrap justify-center gap-3">
            <Link href="/upload" className="rounded-lg bg-white px-5 py-3 font-semibold text-bordeaux transition hover:bg-paper">
              Start from documents
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

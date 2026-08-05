"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { assess, getIndustries, type Assessment, type Industry } from "@/lib/api";
import { money, moneyCompact, num, pct } from "@/lib/format";
import { useSession } from "@/lib/session";
import { ErrorPanel, LoadingPanel } from "@/components/StatePanels";
import { Card, Eyebrow } from "@/components/ui";

/**
 * Per-domain deep dive. Shows this domain's calibration, its share of the tail,
 * and which of its own parameters the answer depends on, all in the industry's
 * vocabulary.
 */
export default function EnginePage({ params }: { params: { engine: string } }) {
  const { engine } = params;
  const { industry, answers, ready } = useSession();
  const [pack, setPack] = useState<Industry | null>(null);
  const [data, setData] = useState<Assessment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready || !industry) return;
    Promise.all([getIndustries(), assess({ industry, answers })])
      .then(([r, a]) => {
        setPack(r.industries.find((p) => p.id === industry) || null);
        setData(a);
      })
      .catch((e) => setError(e.message));
  }, [ready, industry]); // eslint-disable-line react-hooks/exhaustive-deps

  const binding = pack?.engines.find((e) => e.engine === engine);
  const contribution = data?.domain_contributions.find((d) => d.domain === engine);
  const marginal = data?.assumptions.domains?.find((d: any) => d.key === engine);
  const rows = useMemo(
    () => (data?.sensitivity || []).filter((r) => r.engine === engine),
    [data, engine]
  );

  if (ready && !industry) {
    return (
      <div className="container-x py-20 text-center">
        <h1 className="font-display text-2xl font-bold text-ink">Pick an industry first</h1>
        <Link href="/start" className="mt-5 inline-block rounded-lg bg-brand px-5 py-3 font-semibold text-white hover:bg-brand-deep">
          Choose your industry
        </Link>
      </div>
    );
  }

  return (
    <div className="container-x py-10">
      <Link href="/dashboard" className="font-mono text-[0.7rem] text-muted hover:text-brand">← Dashboard</Link>

      {error && <div className="mt-8"><ErrorPanel error={error} /></div>}
      {!data && !error && <div className="mt-8"><LoadingPanel title="Running the model" detail="Recomputing this domain in the context of your full portfolio." /></div>}

      {data && !binding && (
        <div className="mt-10">
          <h1 className="font-display text-2xl font-bold text-ink">Not part of this industry</h1>
          <p className="mt-2 text-muted">
            {data.industry_name} does not run a model called “{engine}”.
          </p>
        </div>
      )}

      {data && binding && (
        <>
          <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-2xl">
              <Eyebrow>{data.industry_name}</Eyebrow>
              <h1 className="mt-2 font-display text-4xl font-bold tracking-tight text-ink">{binding.label}</h1>
              <p className="mt-3 text-muted">{binding.description}</p>
            </div>
            <div className="flex flex-col items-end gap-0.5 font-mono text-[0.66rem] text-muted tnum">
              <span>{engine}</span>
              <span>seed {data.seed}</span>
              <span>{data.n_sims.toLocaleString("en-US")} scenarios</span>
            </div>
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-3">
            <Card className="p-6">
              <Eyebrow>Expected annual loss</Eyebrow>
              <div className="mt-1 font-display text-3xl font-bold tabular-nums text-ink">
                {money(contribution?.expected_annual_loss ?? 0)}
              </div>
              <p className="mt-2 text-xs text-muted">
                Frequency times magnitude, before any correlation with your other domains.
              </p>
            </Card>
            <Card className="p-6">
              <Eyebrow>Share of a typical year</Eyebrow>
              <div className="mt-1 font-display text-3xl font-bold tabular-nums text-ink">
                {pct(contribution?.base_share ?? 0)}
              </div>
              <p className="mt-2 text-xs text-muted">Of total expected loss across all domains.</p>
            </Card>
            <Card className="p-6">
              <Eyebrow>Share of the P95 tail</Eyebrow>
              <div
                className={`mt-1 font-display text-3xl font-bold tabular-nums ${
                  (contribution?.tail_share ?? 0) > (contribution?.base_share ?? 0) ? "text-amber" : "text-ink"
                }`}
              >
                {pct(contribution?.tail_share ?? 0)}
              </div>
              <p className="mt-2 text-xs text-muted">
                {(contribution?.tail_share ?? 0) > (contribution?.base_share ?? 0)
                  ? "Grows in the tail: this shows up when things are already bad."
                  : "Shrinks in the tail: less of a driver when things go wrong."}
              </p>
            </Card>
          </div>

          <div className="mt-8 grid gap-8 lg:grid-cols-2">
            {marginal && (
              <Card className="p-6">
                <Eyebrow>Calibration</Eyebrow>
                <h2 className="mt-1 font-display text-xl font-bold text-ink">What we assumed</h2>
                <p className="mt-2 text-sm text-muted">
                  A starting estimate, not measured data. Change your intake answers and these move.
                </p>
                <dl className="mt-5 space-y-2.5 text-sm">
                  {[
                    ["Events per year (most likely)", num(marginal.lef_mode, 2)],
                    ["Events per year (range)", `${num(marginal.lef_min, 2)} to ${num(marginal.lef_max, 2)}`],
                    ["Typical cost per event", money(marginal.magnitude_mode)],
                    ["Bad case per event (P90)", money(marginal.magnitude_p90)],
                  ].map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-4 border-b border-rule/60 pb-2">
                      <dt className="text-ink/80">{k}</dt>
                      <dd className="font-mono tabular-nums text-muted">{v}</dd>
                    </div>
                  ))}
                </dl>
                <Link href="/intake" className="link-underline mt-4 inline-block text-sm text-brand">
                  Adjust the answers behind these
                </Link>
              </Card>
            )}

            <Card className="p-6">
              <Eyebrow>Sensitivity</Eyebrow>
              <h2 className="mt-1 font-display text-xl font-bold text-ink">What this domain hinges on</h2>
              <p className="mt-2 text-sm text-muted">
                Each parameter shifted 25% in both directions, measured on your portfolio P95.
              </p>
              <div className="mt-5 space-y-2.5">
                {rows.map((r) => {
                  const max = Math.max(...rows.map((x) => x.impact), 1);
                  return (
                    <div key={r.parameter}>
                      <div className="flex items-baseline justify-between gap-3 text-sm">
                        <span className="truncate text-ink/85">{r.parameter_label.split(": ")[1] || r.parameter}</span>
                        <span className="shrink-0 font-mono text-xs tabular-nums text-muted">
                          {moneyCompact(r.impact)}
                        </span>
                      </div>
                      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-rule">
                        <div className="h-full rounded-full bg-brand" style={{ width: `${Math.max(3, (r.impact / max) * 100)}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          </div>

          <div className="mt-8">
            <Eyebrow>Other domains in {data.industry_name}</Eyebrow>
            <div className="mt-3 flex flex-wrap gap-2">
              {data.domain_contributions
                .filter((d) => d.domain !== engine)
                .map((d) => (
                  <Link
                    key={d.domain}
                    href={`/analyze/${d.domain}`}
                    className="rounded-lg border border-rule bg-surface px-3 py-1.5 text-sm text-ink/80 transition-colors hover:border-brand hover:text-brand"
                  >
                    {d.label}
                  </Link>
                ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

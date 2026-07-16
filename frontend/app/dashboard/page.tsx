"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { assess, type AssessResponse } from "@/lib/api";
import { money, moneyCompact, pct } from "@/lib/format";
import { Badge, Button, Card, Eyebrow, RiskBar, SectionHeading } from "@/components/ui";
import { ErrorPanel, LoadingPanel } from "@/components/StatePanels";
import { InterpretationPanel } from "@/components/InterpretationPanel";
import { CorrelationMatrix } from "@/components/CorrelationMatrix";
import { CompositeHeadline } from "@/components/dashboard/CompositeHeadline";
import { DottedWaves } from "@/components/DottedWaves";
import { ScrollFloat } from "@/components/ScrollFloat";

const FORMATS = [
  { id: "executive_summary", label: "Executive summary" },
  { id: "one_pager", label: "One-pager" },
  { id: "list", label: "List" },
];

export default function DashboardPage() {
  const [data, setData] = useState<AssessResponse | null>(null);
  const [started, setStarted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [format, setFormat] = useState("executive_summary");
  const overridesRef = useRef<Record<string, number>>({});
  const debounce = useRef<ReturnType<typeof setTimeout>>();

  const load = (opts?: { correlation_overrides?: Record<string, number>; output_format?: string }) => {
    setStarted(true);
    setLoading(true);
    setError(null);
    assess({
      correlation_overrides: opts?.correlation_overrides ?? overridesRef.current,
      output_format: opts?.output_format ?? format,
    })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  // Only auto-run when the user arrived here intending to run (from Upload).
  useEffect(() => {
    if (typeof window !== "undefined" && new URLSearchParams(window.location.search).get("run") === "1") {
      load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onCorrelationChange = (overrides: Record<string, number>) => {
    overridesRef.current = overrides;
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => load({ correlation_overrides: overrides }), 250);
  };

  const maxTail = useMemo(
    () => (data ? Math.max(...data.ranked.map((r) => r.output.risk_summary?.p95_loss || 0)) : 1),
    [data]
  );

  return (
    <div className="container-x py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Eyebrow>Composite assessment · Acme Industrial Distribution (sample)</Eyebrow>
          <ScrollFloat as="h1" className="mt-2 font-display text-4xl font-bold tracking-tight sm:text-5xl"
            segments={[{ text: "Risk", className: "text-ink" }, { text: "dashboard", className: "text-bordeaux" }]} />
        </div>
        {data && (
          <div className="flex items-center gap-2">
            <span className="font-mono text-[0.66rem] text-muted">Deliver as</span>
            <div className="flex rounded-lg border border-mist bg-surface p-0.5">
              {FORMATS.map((f) => (
                <button
                  key={f.id}
                  onClick={() => {
                    setFormat(f.id);
                    load({ output_format: f.id });
                  }}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                    format === f.id ? "bg-bordeaux text-white" : "text-muted hover:text-ink"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Intentional start state, no auto-run before the user asks. */}
      {!started && !data && (
        <div className="relative mt-8 overflow-hidden rounded-2xl border border-mist bg-surface p-10 shadow-card">
          <DottedWaves corner="br" className="pointer-events-none absolute -bottom-12 -right-8 h-64 w-64" opacity={0.3} />
          <div className="relative max-w-xl">
            <h2 className="font-display text-2xl font-bold text-ink">Run the composite assessment</h2>
            <p className="mt-3 text-muted">
              This runs all six domain models plus the cross-domain correlation on the sample industrial
              distributor profile, roughly 20,000 scenarios per domain. Nothing runs until you start it.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button onClick={() => load()}>Run assessment →</Button>
              <Button href="/upload" variant="outline">Start from your documents</Button>
            </div>
            <p className="mt-4 font-mono text-[0.66rem] text-muted">
              Tip: upload documents first to run the assessment on your own numbers.
            </p>
          </div>
        </div>
      )}

      {loading && !data && <div className="mt-8"><LoadingPanel /></div>}
      {error && <div className="mt-8"><ErrorPanel error={error} onRetry={() => load()} /></div>}

      {data && (
        <div className={`mt-8 space-y-10 ${loading ? "opacity-60 transition-opacity" : ""}`}>
          {data.composite && !data.composite.insufficient_domains && (
            <CompositeHeadline c={data.composite} />
          )}

          {/* Domains + correlation */}
          <div className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
            <div>
              <SectionHeading eyebrow="By domain" title="Standalone exposure" intro="Ranked by P95 tail. Open any domain to interrogate its assumptions." />
              <div className="mt-5 space-y-3">
                {data.ranked.map((r) => {
                  const rs = r.output.risk_summary;
                  return (
                    <Link
                      key={r.key}
                      href={`/analyze/${r.key}`}
                      className="block rounded-xl border border-mist bg-surface p-4 shadow-card transition hover:border-bordeaux/40"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-ink">{r.name}</span>
                        <span className="font-mono text-sm tabular-nums text-ink">{money(rs?.expected_loss)}</span>
                      </div>
                      <div className="mt-2.5">
                        <RiskBar value={rs?.p95_loss || 0} max={maxTail} tone="ochre" />
                      </div>
                      <div className="mt-1.5 flex justify-between font-mono text-[0.66rem] text-muted tnum">
                        <span>{r.domain}</span>
                        <span>P95 tail {moneyCompact(rs?.p95_loss)}</span>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>

            <div>
              <SectionHeading eyebrow="The compounding" title="Correlation" intro="Edit a cell to change how two risks move together, the assessment re-runs." />
              {data.composite?.correlation_matrix && (
                <Card className="mt-5 p-5">
                  <CorrelationMatrix
                    keys={data.composite.correlation_matrix.keys}
                    labels={data.composite.correlation_matrix.labels}
                    matrix={data.composite.correlation_matrix.matrix}
                    onChange={onCorrelationChange}
                  />
                  {data.composite.correlation_matrix.psd_adjusted && (
                    <p className="mt-3 font-mono text-[0.66rem] text-ochre">
                      Matrix was projected to the nearest valid (positive-semi-definite) correlation structure.
                    </p>
                  )}
                </Card>
              )}
              {data.composite?.top_pairs && (
                <Card className="mt-4 p-5">
                  <Eyebrow>Top compounding pairs</Eyebrow>
                  <div className="mt-3 space-y-2.5">
                    {data.composite.top_pairs.slice(0, 4).map((p, i) => (
                      <div key={i} className="flex items-center justify-between text-sm">
                        <span className="text-ink/80">
                          {p.a_label} <span className="text-muted">×</span> {p.b_label}
                        </span>
                        <span className="font-mono tabular-nums text-muted">
                          ρ {p.rho.toFixed(2)} · {pct(p.share)}
                        </span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          </div>

          {/* Interpretation + recommendations */}
          <div className="grid gap-8 lg:grid-cols-2">
            <div>
              <SectionHeading eyebrow="The read" title="What this means" />
              <div className="mt-5">
                <InterpretationPanel text={data.interpretation} />
              </div>
            </div>
            <div>
              <SectionHeading eyebrow="Action" title="Ranked recommendations" intro="Each carries a dollar impact and its tail, never a bare 'you should'." />
              <div className="mt-5 space-y-3">
                {data.recommendations.map((r) => (
                  <Card key={r.rank} className="p-4">
                    <div className="flex items-start gap-3">
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-bordeaux/10 font-mono text-xs font-semibold text-bordeaux">
                        {r.rank}
                      </span>
                      <div className="flex-1">
                        <div className="font-medium text-ink">{r.title}</div>
                        <p className="mt-1 text-xs text-muted">{r.rationale}</p>
                        <div className="mt-2 font-mono text-[0.68rem] tabular-nums text-bordeaux">
                          {money(r.impact_expected)} expected
                          {r.impact_tail ? ` · up to ${money(r.impact_tail)} at P95` : ""}
                        </div>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          </div>

          {/* Delivery */}
          <DeliveryView data={data} />
        </div>
      )}
    </div>
  );
}

function DeliveryView({ data }: { data: AssessResponse }) {
  const d = data.delivery;
  return (
    <Card className="p-6 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Eyebrow>Deliverable · {d.format.replace(/_/g, " ")}</Eyebrow>
          <h3 className="mt-1 font-display text-2xl font-semibold text-ink">{d.title}</h3>
        </div>
        <div className="flex gap-2">
          {Object.entries(d.export).map(([k, v]) => (
            <span
              key={k}
              className="inline-flex items-center gap-1.5 rounded-md border border-mist px-2.5 py-1 font-mono text-[0.66rem] text-muted"
              title={v.available ? "Available" : `${v.tier} tier`}
            >
              {k.replace(/_/g, " ")} {v.available ? "✓" : `· ${v.tier}`}
            </span>
          ))}
        </div>
      </div>

      {d.headline && <p className="mt-4 font-display text-lg text-bordeaux">{d.headline}</p>}

      <div className="mt-5 grid gap-3 sm:grid-cols-4">
        {d.key_numbers.map((k) => (
          <div key={k.label} className="rounded-lg border border-mist bg-paper p-3">
            <div className="font-mono text-[0.6rem] uppercase tracking-wide text-muted">{k.label}</div>
            <div className="mt-1 font-display text-xl font-semibold tabular-nums text-ink">{k.value}</div>
          </div>
        ))}
      </div>

      {d.view !== "list" && (
        <p className="mt-5 whitespace-pre-line leading-relaxed text-ink/90">{d.interpretation}</p>
      )}

      <div className="mt-5 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-mist text-left font-mono text-[0.66rem] uppercase tracking-wide text-muted">
              <th className="pb-2">Domain</th>
              <th className="pb-2 text-right">Expected</th>
              <th className="pb-2 text-right">Tail · P95</th>
            </tr>
          </thead>
          <tbody className="tnum">
            {d.domain_table.map((row) => (
              <tr key={row.domain} className="border-b border-mist/60">
                <td className="py-2 text-ink">{row.domain}</td>
                <td className="py-2 text-right font-mono text-ink/80">{row.expected}</td>
                <td className="py-2 text-right font-mono text-ochre">{row.tail_p95}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-5 border-t border-mist pt-4 font-mono text-[0.66rem] text-muted">{d.disclaimer}</p>
    </Card>
  );
}

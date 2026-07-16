"use client";
import { useEffect, useState } from "react";
import { getModels, getTemplates, type ModelSpec, type TemplatesResponse } from "@/lib/api";
import { byType } from "@/lib/format";
import { Badge, Card, Eyebrow } from "@/components/ui";
import { ErrorPanel, LoadingPanel } from "@/components/StatePanels";

export default function MethodologyPage() {
  const [models, setModels] = useState<ModelSpec[] | null>(null);
  const [templates, setTemplates] = useState<TemplatesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getModels(), getTemplates()])
      .then(([m, t]) => {
        setModels(m.models);
        setTemplates(t);
      })
      .catch((e) => setError(e.message));
  }, []);

  const tmplFor = (key: string) => templates?.templates.find((t) => t.model_key === key);

  return (
    <div className="container-x py-12">
      <div className="max-w-2xl">
        <Eyebrow>Glass box</Eyebrow>
        <h1 className="mt-2 font-display text-4xl font-bold tracking-tight text-ink">Methodology</h1>
        <p className="mt-3 text-muted">
          Every number this product shows comes from one of these validated, seeded functions. The AI
          selects a model and interprets its output, it never writes the math and never invents a
          figure. This page is generated directly from the running model registry, so it can&apos;t
          drift from the code.
        </p>
      </div>

      {error && <div className="mt-8"><ErrorPanel error={error} /></div>}
      {!models && !error && <div className="mt-8"><LoadingPanel title="Loading the registry" detail="Fetching every model's specification." /></div>}

      {models && (
        <div className="mt-10 space-y-5">
          {models.map((m) => {
            const t = tmplFor(m.key);
            return (
              <Card key={m.key} className="p-6">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="font-display text-xl font-bold text-ink">{m.name}</h2>
                      <Badge tone="muted">{m.domain}</Badge>
                      {!m.runnable && <Badge tone="bordeaux">meta-model</Badge>}
                    </div>
                    <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted">{m.method}</p>
                  </div>
                  <div className="flex flex-col items-end gap-1 font-mono text-[0.66rem] text-muted tnum">
                    <span className="text-ink">v{m.version}</span>
                    <span>seed {m.seed}</span>
                    {t?.authored_by && <span className="text-right">{t.authored_by}</span>}
                  </div>
                </div>

                <div className="mt-5 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
                  {/* Parameters / assumptions */}
                  <div>
                    <div className="font-mono text-[0.66rem] uppercase tracking-wide text-muted">
                      Parameters &amp; default assumptions
                    </div>
                    {m.parameters.length ? (
                      <div className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
                        {m.parameters.map((p) => (
                          <div key={p.name} className="flex justify-between gap-3 border-b border-mist/60 py-1 text-sm">
                            <span className="text-ink/80">{p.label}</span>
                            <span className="font-mono tabular-nums text-muted">
                              {p.type === "entity_list"
                                ? `${(p.default as any[])?.length ?? 0} rows`
                                : byType(p.default, p.type)}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-2 text-sm text-muted">Consumes the per-domain loss distributions.</p>
                    )}
                  </div>

                  {/* Outputs + accuracy */}
                  <div>
                    <div className="font-mono text-[0.66rem] uppercase tracking-wide text-muted">Reports</div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {m.outputs.map((o) => (
                        <span key={o.key} className="rounded-md border border-mist bg-paper px-2 py-0.5 font-mono text-[0.66rem] text-ink/70">
                          {o.label}
                        </span>
                      ))}
                    </div>
                    {t?.accuracy && (
                      <div className="mt-4">
                        <div className="font-mono text-[0.66rem] uppercase tracking-wide text-muted">
                          Tracked accuracy · {t.backtests} backtests
                        </div>
                        <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[0.7rem] tabular-nums text-ink/80">
                          {Object.entries(t.accuracy).map(([k, v]) => (
                            <span key={k}>
                              <span className="text-muted">{k}</span> {typeof v === "number" ? v : String(v)}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {m.docstring && (
                  <details className="mt-4 border-t border-mist pt-3">
                    <summary className="cursor-pointer font-mono text-[0.7rem] uppercase tracking-wide text-muted hover:text-bordeaux">
                      Method detail
                    </summary>
                    <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-ink/80">{m.docstring}</p>
                  </details>
                )}
              </Card>
            );
          })}

          {templates && (
            <Card className="border-dashed p-6">
              <Eyebrow>Template &amp; accuracy database</Eyebrow>
              <p className="mt-2 max-w-3xl text-sm text-muted">{templates.note}</p>
              <p className="mt-2 font-mono text-[0.66rem] text-muted">
                Authoring pipeline (AI drafts → human review → tests → register):{" "}
                {templates.authoring_pipeline_enabled ? "enabled" : "scaffolded"}.
              </p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

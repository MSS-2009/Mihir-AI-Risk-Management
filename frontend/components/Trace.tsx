// Traceability, surfaced, not buried (rule §4.6).

export function Trace({
  trace,
}: {
  trace?: { model_key?: string; model?: string; version?: string; seed?: number; n_sims?: number };
}) {
  if (!trace) return null;
  const items = [
    ["model", trace.model_key || trace.model],
    ["version", trace.version ? `v${trace.version}` : undefined],
    ["seed", trace.seed],
    ["scenarios", trace.n_sims?.toLocaleString("en-US")],
  ].filter(([, v]) => v !== undefined && v !== null);

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[0.66rem] text-muted">
      {items.map(([k, v]) => (
        <span key={k as string} className="tnum">
          <span className="text-muted/60">{k}</span> {v as string}
        </span>
      ))}
    </div>
  );
}

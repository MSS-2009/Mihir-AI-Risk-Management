"use client";
import { useState } from "react";
import type { Estimation } from "@/lib/api";
import { pct } from "@/lib/format";

/**
 * Where every number came from.
 *
 * The interface principle here is that provenance reads as strength, not
 * apology. "Twelve observations over two years, 44% weight on your data" is a
 * statement of rigour and is designed as one. The inverse, a parameter still on
 * our published estimate, is not hidden either: it says which system would
 * change that, because a customer who can see what connecting more would buy
 * them is the only customer who connects more.
 *
 * Deliberately counted per parameter rather than per engine. Finance data
 * routinely evidences how often something happens and says nothing about what
 * it costs, so an engine is honestly half measured, and rounding that up to
 * "measured" would overstate roughly half of what the product produces.
 */
export function ProvenancePanel({ e }: { e: Estimation }) {
  const [open, setOpen] = useState(false);
  const { coverage: c } = e;
  const known = c.measured + c.blended;

  return (
    <section className="rounded-2xl border border-rule bg-surface p-6 shadow-card">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="eyebrow">Where these numbers come from</div>
          <h2 className="mt-1 font-display text-xl font-bold text-ink">
            {known > 0 ? (
              <>
                <span className="text-brand tabular-nums">{known}</span> of{" "}
                <span className="tabular-nums">{c.total}</span> parameters are estimated from
                your own history
              </>
            ) : (
              <>Every parameter is still our published starting estimate</>
            )}
          </h2>
        </div>
        {e.snapshot && (
          <div className="text-right font-mono text-[0.62rem] text-muted">
            <div>{e.snapshot.window_years} years observed</div>
            <div>
              {e.snapshot.window_start} to {e.snapshot.window_end}
            </div>
          </div>
        )}
      </div>

      {/* One bar, three states. Reads as coverage earned, not as a warning. */}
      <div className="mt-5 flex h-2.5 overflow-hidden rounded-full bg-rule">
        {([
          ["measured", c.measured, "bg-brand"],
          ["blended", c.blended, "bg-brand/45"],
          ["prior", c.prior, "bg-rule"],
        ] as const).map(([label, n, cls]) =>
          n > 0 ? (
            <div key={label} className={cls} style={{ width: `${(n / c.total) * 100}%` }} />
          ) : null
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[0.62rem] text-muted">
        <Key className="bg-brand" label="measured" n={c.measured} />
        <Key className="bg-brand/45" label="blended" n={c.blended} />
        <Key className="bg-rule" label="our estimate" n={c.prior} />
      </div>

      <button
        onClick={() => setOpen((s) => !s)}
        aria-expanded={open}
        className="mt-4 font-mono text-[0.62rem] uppercase tracking-wide text-muted hover:text-brand"
      >
        {open ? "hide parameter detail" : "show every parameter"}
      </button>

      {open && (
        <div className="mt-3 overflow-x-auto rounded-xl border border-rule">
          <table className="w-full min-w-[680px] text-sm">
            <thead>
              <tr className="border-b border-rule bg-raised">
                {["Parameter", "Source", "Observations", "Weight on your data", "Value"].map((h) => (
                  <th
                    key={h}
                    className="px-3 py-2 text-left font-mono text-[0.58rem] uppercase tracking-wide text-muted"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {e.parameters.map((p) => (
                <tr key={`${p.engine}-${p.parameter}`} className="border-b border-rule/60 last:border-0">
                  <td className="px-3 py-2">
                    <div className="text-ink">{p.engine.replace(/_/g, " ")}</div>
                    <div className="font-mono text-[0.58rem] text-muted">{p.parameter}</div>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 font-mono text-[0.55rem] uppercase tracking-wide ${
                        p.provenance === "measured"
                          ? "bg-brand/12 text-brand"
                          : p.provenance === "blended"
                          ? "bg-brand/[0.07] text-brand/80"
                          : "bg-rule text-muted"
                      }`}
                    >
                      {p.provenance === "prior" ? "our estimate" : p.provenance}
                    </span>
                    {p.source && (
                      <div className="mt-1 font-mono text-[0.55rem] text-muted">{p.source}</div>
                    )}
                    {/* A parameter on our estimate always says why, so the gap
                        is actionable rather than mysterious. */}
                    {p.provenance === "prior" && p.reason && (
                      <div className="mt-1 max-w-xs text-[0.62rem] leading-snug text-muted">
                        {p.reason}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs tabular-nums text-ink">
                    {p.provenance === "prior" ? (
                      <span className="text-muted">-</span>
                    ) : (
                      <>
                        {p.n_observations}
                        <span className="text-muted"> over {p.window_years}y</span>
                      </>
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs tabular-nums">
                    {p.provenance === "prior" ? (
                      <span className="text-muted">-</span>
                    ) : (
                      <span className="text-ink">{pct(p.weight_on_data, 0)}</span>
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs tabular-nums text-ink">
                    {p.value !== null && p.prior_value !== null && p.provenance !== "prior" ? (
                      <>
                        <span className="text-muted">{fmt(p.prior_value)}</span>
                        <span className="text-muted"> → </span>
                        {fmt(p.value)}
                      </>
                    ) : (
                      <span className="text-muted">{p.value !== null ? fmt(p.value) : "-"}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {c.unlocks.length > 0 && (
        <div className="mt-4 border-t border-rule pt-3">
          <div className="eyebrow">What would improve coverage</div>
          <ul className="mt-1.5 space-y-1">
            {c.unlocks.slice(0, 5).map((u) => (
              <li key={u} className="flex gap-2 text-xs leading-relaxed text-muted">
                <span aria-hidden className="mt-[0.4rem] h-1 w-1 shrink-0 rounded-full bg-brand" />
                {u}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="mt-4 border-t border-rule pt-3 font-mono text-[0.6rem] leading-relaxed text-muted">
        {e.basis}
      </p>
    </section>
  );
}

function Key({ className, label, n }: { className: string; label: string; n: number }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`h-2 w-2 rounded-full ${className}`} />
      <span className="tabular-nums text-ink">{n}</span> {label}
    </span>
  );
}

/** Frequencies are small rates; magnitudes are dollars. One formatter, read from scale. */
function fmt(v: number): string {
  if (Math.abs(v) >= 10_000) return `$${Math.round(v).toLocaleString("en-US")}`;
  return v.toFixed(2);
}

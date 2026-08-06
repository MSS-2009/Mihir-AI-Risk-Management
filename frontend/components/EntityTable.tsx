"use client";
import { money, pct } from "@/lib/format";

/**
 * The operator's own book: vendors, import lines, sites. This is what makes a
 * deep pack feel built for them, so it is a real editable table rather than a
 * single aggregate percentage.
 */
export function EntityTable({
  rows,
  fields,
  onChange,
  addLabel = "Add row",
}: {
  rows: Record<string, any>[];
  fields: { name: string; label: string; type: string; unit?: string; choices?: string[] }[];
  onChange: (rows: Record<string, any>[]) => void;
  addLabel?: string;
}) {
  const set = (i: number, k: string, v: any) =>
    onChange(rows.map((r, idx) => (idx === i ? { ...r, [k]: v } : r)));
  const remove = (i: number) => onChange(rows.filter((_, idx) => idx !== i));
  const add = () => {
    const blank: Record<string, any> = {};
    fields.forEach((f) => {
      blank[f.name] = f.type === "text" ? "" : f.type === "bool" ? false : f.type === "choice" ? (f.choices?.[0] ?? "") : 0;
    });
    onChange([...rows, blank]);
  };

  return (
    <div>
      <div className="overflow-x-auto rounded-xl border border-rule">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-rule bg-raised">
              {fields.map((f) => (
                <th key={f.name} className="px-3 py-2 text-left font-mono text-[0.6rem] uppercase tracking-wide text-muted">
                  {f.label}{f.unit ? ` (${f.unit})` : ""}
                </th>
              ))}
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-rule/60 last:border-0">
                {fields.map((f) => (
                  <td key={f.name} className="px-2 py-1.5">
                    {f.type === "bool" ? (
                      <input
                        type="checkbox"
                        checked={!!r[f.name]}
                        onChange={(e) => set(i, f.name, e.target.checked)}
                        aria-label={`${f.label} for row ${i + 1}`}
                        className="h-4 w-4 accent-brand"
                      />
                    ) : f.type === "choice" ? (
                      <select
                        value={String(r[f.name] ?? "")}
                        onChange={(e) => set(i, f.name, e.target.value)}
                        aria-label={`${f.label} for row ${i + 1}`}
                        className="w-full rounded border border-rule bg-surface px-2 py-1 font-mono text-xs text-ink outline-none focus:border-brand"
                      >
                        {(f.choices || []).map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                    ) : f.type === "text" ? (
                      <input
                        value={String(r[f.name] ?? "")}
                        onChange={(e) => set(i, f.name, e.target.value)}
                        aria-label={`${f.label} for row ${i + 1}`}
                        className="w-full rounded border border-rule bg-surface px-2 py-1 text-xs text-ink outline-none focus:border-brand"
                      />
                    ) : (
                      <input
                        inputMode="decimal"
                        value={
                          f.type === "currency"
                            ? Number(r[f.name] ?? 0).toLocaleString("en-US")
                            : f.type === "percent"
                            ? String(Math.round(Number(r[f.name] ?? 0) * 100))
                            : String(r[f.name] ?? 0)
                        }
                        onChange={(e) => {
                          const n = parseFloat(e.target.value.replace(/[^0-9.]/g, "")) || 0;
                          set(i, f.name, f.type === "percent" ? n / 100 : n);
                        }}
                        aria-label={`${f.label} for row ${i + 1}`}
                        className="w-full rounded border border-rule bg-surface px-2 py-1 text-right font-mono text-xs tabular-nums text-ink outline-none focus:border-brand"
                      />
                    )}
                  </td>
                ))}
                <td className="px-1">
                  <button
                    onClick={() => remove(i)}
                    aria-label={`Remove row ${i + 1}`}
                    className="rounded px-1.5 py-1 text-xs text-muted hover:text-amber"
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button onClick={add} className="mt-2 font-mono text-[0.68rem] uppercase tracking-wide text-brand hover:text-brand-deep">
        + {addLabel}
      </button>
    </div>
  );
}

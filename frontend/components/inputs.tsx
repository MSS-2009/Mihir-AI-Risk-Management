"use client";
import { useId } from "react";
import { pct } from "@/lib/format";

/** Formatted currency input, shows $8,000,000, never 8000000. */
export function CurrencyInput({
  label,
  value,
  onChange,
  help,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  help?: string;
}) {
  const id = useId();
  return (
    <label htmlFor={id} className="block">
      <span className="block text-sm font-medium text-ink">{label}</span>
      <div className="mt-1 flex items-center rounded-lg border border-rule bg-surface focus-within:border-brand">
        <span className="pl-3 font-mono text-sm text-muted">$</span>
        <input
          id={id}
          inputMode="numeric"
          value={value.toLocaleString("en-US")}
          onChange={(e) => {
            const n = parseFloat(e.target.value.replace(/[^0-9.]/g, ""));
            onChange(Number.isFinite(n) ? n : 0);
          }}
          className="w-full bg-transparent px-2 py-2 font-mono text-sm tabular-nums text-ink outline-none"
        />
      </div>
      {help && <span className="mt-1 block text-xs text-muted">{help}</span>}
    </label>
  );
}

/** Percentage slider with a live value. */
export function PercentSlider({
  label,
  value,
  onChange,
  min = 0,
  max = 1,
  step = 0.01,
  help,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  help?: string;
}) {
  const id = useId();
  return (
    <label htmlFor={id} className="block">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium text-ink">{label}</span>
        <span className="font-mono text-sm tabular-nums text-brand">{pct(value, value < 0.1 ? 1 : 0)}</span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="mt-2 w-full accent-brand"
      />
      {help && <span className="mt-1 block text-xs text-muted">{help}</span>}
    </label>
  );
}

/** Plain number / integer input. */
export function NumberInput({
  label,
  value,
  onChange,
  unit,
  step = 1,
  help,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  unit?: string;
  step?: number;
  help?: string;
}) {
  const id = useId();
  return (
    <label htmlFor={id} className="block">
      <span className="block text-sm font-medium text-ink">{label}</span>
      <div className="mt-1 flex items-center rounded-lg border border-rule bg-surface focus-within:border-brand">
        <input
          id={id}
          type="number"
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          className="w-full bg-transparent px-3 py-2 font-mono text-sm tabular-nums text-ink outline-none"
        />
        {unit && <span className="pr-3 font-mono text-xs text-muted">{unit}</span>}
      </div>
      {help && <span className="mt-1 block text-xs text-muted">{help}</span>}
    </label>
  );
}

/** Named-entity list (suppliers, countries), add/remove rows. */
export function EntityList({
  label,
  rows,
  fields,
  onChange,
}: {
  label: string;
  rows: Record<string, any>[];
  fields: { name: string; label: string; type: string }[];
  onChange: (rows: Record<string, any>[]) => void;
}) {
  const update = (i: number, key: string, v: any) => {
    const next = rows.map((r, idx) => (idx === i ? { ...r, [key]: v } : r));
    onChange(next);
  };
  const remove = (i: number) => onChange(rows.filter((_, idx) => idx !== i));
  const add = () => {
    const blank: Record<string, any> = {};
    fields.forEach((f) => (blank[f.name] = f.type === "text" ? "" : 0));
    onChange([...rows, blank]);
  };

  return (
    <div>
      <span className="block text-sm font-medium text-ink">{label}</span>
      <div className="mt-2 space-y-2">
        {rows.map((r, i) => (
          <div key={i} className="flex flex-wrap items-end gap-2 rounded-lg border border-rule bg-raised p-2.5">
            {fields.map((f) => (
              <label key={f.name} className="flex-1 basis-24">
                <span className="block font-mono text-[0.6rem] uppercase tracking-wide text-muted">{f.label}</span>
                <input
                  value={r[f.name] ?? ""}
                  onChange={(e) =>
                    update(
                      i,
                      f.name,
                      f.type === "text" ? e.target.value : parseFloat(e.target.value.replace(/[^0-9.]/g, "")) || 0
                    )
                  }
                  className="mt-0.5 w-full rounded border border-rule bg-surface px-2 py-1 font-mono text-xs tabular-nums outline-none focus:border-brand"
                />
              </label>
            ))}
            <button
              onClick={() => remove(i)}
              className="rounded px-2 py-1 text-xs text-muted hover:text-amber"
              aria-label={`Remove ${r.name || "row"}`}
            >
              Remove
            </button>
          </div>
        ))}
      </div>
      <button onClick={add} className="mt-2 text-sm font-medium text-brand hover:text-brand-deep">
        + Add {label.replace(/s$/, "").toLowerCase()}
      </button>
    </div>
  );
}

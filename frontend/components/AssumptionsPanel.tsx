"use client";
import { useState } from "react";
import type { ParamSpec } from "@/lib/api";
import { CurrencyInput, EntityList, NumberInput, PercentSlider } from "./inputs";

/**
 * Always-visible, always-editable assumptions. Changing one re-runs the analysis
 * (the parent debounces). Advanced params are tucked behind a disclosure so the
 * primary inputs read like a form a CFO would fill in.
 */
export function AssumptionsPanel({
  params,
  values,
  onChange,
}: {
  params: ParamSpec[];
  values: Record<string, any>;
  onChange: (values: Record<string, any>) => void;
}) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const set = (name: string, v: any) => onChange({ ...values, [name]: v });

  const primary = params.filter((p) => !p.advanced);
  const advanced = params.filter((p) => p.advanced);

  const render = (p: ParamSpec) => {
    const v = values[p.name] ?? p.default;
    if (p.type === "currency")
      return <CurrencyInput key={p.name} label={p.label} value={Number(v)} onChange={(x) => set(p.name, x)} help={p.help || undefined} />;
    if (p.type === "percent")
      return (
        <PercentSlider
          key={p.name}
          label={p.label}
          value={Number(v)}
          min={p.min ?? (p.name.includes("correlation") ? -1 : 0)}
          max={p.max ?? 1}
          onChange={(x) => set(p.name, x)}
          help={p.help || undefined}
        />
      );
    if (p.type === "entity_list")
      return (
        <div key={p.name} className="sm:col-span-2">
          <EntityList label={p.label} rows={(v as any[]) || []} fields={p.fields || []} onChange={(x) => set(p.name, x)} />
        </div>
      );
    return (
      <NumberInput key={p.name} label={p.label} value={Number(v)} unit={p.unit || undefined} onChange={(x) => set(p.name, x)} help={p.help || undefined} />
    );
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <h3 className="font-display text-lg font-semibold text-ink">Assumptions</h3>
        <span className="font-mono text-[0.66rem] text-muted">edits re-run the model</span>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-5 sm:grid-cols-2">{primary.map(render)}</div>

      {advanced.length > 0 && (
        <div className="mt-5 border-t border-mist pt-4">
          <button
            onClick={() => setShowAdvanced((s) => !s)}
            className="font-mono text-[0.7rem] uppercase tracking-wide text-muted hover:text-bordeaux"
            aria-expanded={showAdvanced}
          >
            {showAdvanced ? "− Hide" : "+ Show"} advanced assumptions ({advanced.length})
          </button>
          {showAdvanced && <div className="mt-4 grid grid-cols-1 gap-5 sm:grid-cols-2">{advanced.map(render)}</div>}
        </div>
      )}
    </div>
  );
}

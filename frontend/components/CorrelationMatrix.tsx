"use client";
import { useState } from "react";

/**
 * The compounding view. Cells are editable, changing a correlation re-runs the
 * assessment. Positive correlations read bordeaux, negative ochre, and the
 * intensity tracks magnitude.
 */
function cellStyle(rho: number): React.CSSProperties {
  if (rho >= 0.999) return { background: "#5E0118", color: "#fff" };
  if (rho >= 0) return { background: `rgba(107,30,50,${0.08 + rho * 0.62})`, color: rho > 0.55 ? "#fff" : "#141110" };
  return { background: `rgba(180,83,9,${0.08 + Math.abs(rho) * 0.55})`, color: "#141110" };
}

export function CorrelationMatrix({
  keys,
  labels,
  matrix,
  onChange,
}: {
  keys: string[];
  labels: string[];
  matrix: number[][];
  onChange?: (overrides: Record<string, number>) => void;
}) {
  const [sel, setSel] = useState<[number, number] | null>(null);
  const [overrides, setOverrides] = useState<Record<string, number>>({});

  const pairKey = (i: number, j: number) => {
    const [a, b] = [keys[i], keys[j]].sort();
    return `${a}|${b}`;
  };
  const rhoAt = (i: number, j: number) => {
    const k = pairKey(i, j);
    return overrides[k] ?? matrix[i][j];
  };

  const setRho = (i: number, j: number, v: number) => {
    const next = { ...overrides, [pairKey(i, j)]: v };
    setOverrides(next);
    onChange?.(next);
  };

  const short = (l: string) => l.split(" ")[0];

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-1">
          <thead>
            <tr>
              <th className="w-24" />
              {labels.map((l, j) => (
                <th key={j} className="px-1 pb-1 font-mono text-[0.6rem] font-normal text-muted">
                  <div className="mx-auto w-10 truncate" title={l}>{short(l)}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {labels.map((l, i) => (
              <tr key={i}>
                <td className="pr-2 text-right font-mono text-[0.62rem] text-muted" title={l}>
                  {short(l)}
                </td>
                {labels.map((_, j) => {
                  const rho = rhoAt(i, j);
                  const isDiag = i === j;
                  const selected = sel && sel[0] === i && sel[1] === j;
                  return (
                    <td key={j}>
                      <button
                        disabled={isDiag}
                        onClick={() => setSel([i, j])}
                        aria-label={`Correlation ${labels[i]} and ${labels[j]}: ${rho.toFixed(2)}`}
                        className={`flex h-9 w-11 items-center justify-center rounded font-mono text-[0.66rem] tabular-nums transition ${
                          isDiag ? "cursor-default opacity-70" : "cursor-pointer hover:ring-2 hover:ring-bordeaux/40"
                        } ${selected ? "ring-2 ring-bordeaux" : ""}`}
                        style={cellStyle(rho)}
                      >
                        {rho.toFixed(2)}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {sel && sel[0] !== sel[1] && (
        <div className="mt-4 rounded-lg border border-mist bg-paper p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-ink">
              {labels[sel[0]]} <span className="text-muted">×</span> {labels[sel[1]]}
            </span>
            <span className="font-mono tabular-nums text-bordeaux">{rhoAt(sel[0], sel[1]).toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={-0.5}
            max={0.95}
            step={0.05}
            value={rhoAt(sel[0], sel[1])}
            onChange={(e) => setRho(sel[0], sel[1], parseFloat(e.target.value))}
            className="mt-3 w-full accent-bordeaux"
            aria-label="Adjust correlation"
          />
          <p className="mt-2 font-mono text-[0.66rem] text-muted">
            Adjusting a correlation re-runs the assessment. Editable defaults come from documented economic linkages.
          </p>
        </div>
      )}
    </div>
  );
}

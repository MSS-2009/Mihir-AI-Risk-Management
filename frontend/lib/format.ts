// Formatting, money is always formatted; a raw float in the UI is a bug.

export function money(n: number | null | undefined, opts?: { sign?: boolean }): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  const s = n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
  return opts?.sign && n > 0 ? `+${s}` : s;
}

export function moneyCompact(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1e6).toFixed(abs >= 1e7 ? 1 : 2)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

export function pct(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return `${(n * 100).toFixed(digits)}%`;
}

export function num(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return n.toLocaleString("en-US", { maximumFractionDigits: digits });
}

/** Format a value by its declared output/param type. */
export function byType(value: unknown, type?: string): string {
  if (value === null || value === undefined) return "-";
  if (type === "currency") return money(Number(value));
  if (type === "percent") return pct(Number(value));
  if (type === "int") return num(Number(value), 0);
  if (type === "number") return num(Number(value));
  return String(value);
}

export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

"use client";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { moneyCompact } from "@/lib/format";

/**
 * Loss exceedance: how much you lose at each percentile, correlated against the
 * same portfolio modelled as independent. The gap between the two lines IS the
 * product's claim, so both are drawn.
 */
export function ExceedanceCurve({
  correlated,
  independent,
  height = 260,
}: {
  correlated: { percentile: number; loss: number }[];
  independent: { percentile: number; loss: number }[];
  height?: number;
}) {
  const data = correlated.map((c, i) => ({
    percentile: c.percentile,
    correlated: c.loss,
    independent: independent[i]?.loss ?? null,
  }));
  const p99 = data[data.length - 1];

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 16, right: 20, bottom: 24, left: 8 }}>
        <CartesianGrid stroke="rgb(var(--rule))" strokeDasharray="2 4" vertical={false} />
        <XAxis
          dataKey="percentile"
          type="number"
          domain={[50, 99]}
          ticks={[50, 75, 90, 95, 99]}
          tickFormatter={(v) => `P${v}`}
          tick={{ fontSize: 11, fill: "rgb(var(--muted))", fontFamily: "var(--font-geist-mono)" }}
          tickLine={false}
          axisLine={{ stroke: "rgb(var(--rule))" }}
          label={{ value: "Percentile", position: "insideBottom", offset: -12, fontSize: 11, fill: "rgb(var(--muted))" }}
        />
        <YAxis
          tickFormatter={(v) => moneyCompact(v)}
          tick={{ fontSize: 11, fill: "rgb(var(--muted))", fontFamily: "var(--font-geist-mono)" }}
          tickLine={false}
          axisLine={false}
          width={58}
          label={{ value: "Annual loss (USD)", angle: -90, position: "insideLeft", fontSize: 11, fill: "rgb(var(--muted))", style: { textAnchor: "middle" } }}
        />
        <Tooltip
          formatter={(v: any, n: any) => [moneyCompact(Number(v)), n === "correlated" ? "Correlated" : "If independent"]}
          labelFormatter={(l) => `P${l}`}
          contentStyle={{
            background: "rgb(var(--surface))",
            border: "1px solid rgb(var(--rule))",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Line
          type="monotone"
          dataKey="independent"
          stroke="rgb(var(--muted))"
          strokeWidth={1.5}
          strokeDasharray="4 4"
          dot={false}
          isAnimationActive={false}
        />
        <Line
          type="monotone"
          dataKey="correlated"
          stroke="rgb(var(--brand))"
          strokeWidth={2.5}
          dot={{ r: 3, fill: "rgb(var(--brand))" }}
          isAnimationActive={false}
        />
        {p99 && <ReferenceDot x={99} y={p99.correlated} r={5} fill="rgb(var(--amber))" stroke="none" />}
      </LineChart>
    </ResponsiveContainer>
  );
}

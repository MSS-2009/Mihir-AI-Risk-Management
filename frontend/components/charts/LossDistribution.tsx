"use client";
import { Area, AreaChart, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { moneyCompact } from "@/lib/format";

/**
 * Loss-distribution density rebuilt from the model's reported quantile grid.
 * Right-skewed by construction (mass near zero + a fat tail). The region beyond
 * P95 is shaded ochre, the tail is the product, so it's the emphasis.
 */
function densityFromQuantiles(q: Record<string, number>): { x: number; y: number }[] {
  const probs = [0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99];
  const vals = [0, q["0.1"], q["0.25"], q["0.5"], q["0.75"], q["0.9"], q["0.95"], q["0.99"]].map(
    (v) => v ?? 0
  );
  const pts: { x: number; y: number }[] = [];
  for (let i = 1; i < probs.length; i++) {
    const dx = Math.max(vals[i] - vals[i - 1], 1);
    const dens = (probs[i] - probs[i - 1]) / dx;
    pts.push({ x: vals[i - 1], y: dens });
    pts.push({ x: vals[i], y: dens });
  }
  // normalize height to ~1 for display
  const maxY = Math.max(...pts.map((p) => p.y), 1e-9);
  return pts.map((p) => ({ x: p.x, y: p.y / maxY }));
}

export function LossDistribution({
  quantiles,
  p95,
  height = 220,
}: {
  quantiles: Record<string, number>;
  p95: number;
  height?: number;
}) {
  const pts = densityFromQuantiles(quantiles);
  const data = pts.map((p) => ({
    x: p.x,
    body: p.x <= p95 ? p.y : null,
    tail: p.x >= p95 ? p.y : null,
  }));
  const tIdx = data.findIndex((d) => d.tail !== null);
  if (tIdx > 0) data[tIdx - 1].tail = data[tIdx - 1].body;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 8 }}>
        <defs>
          <linearGradient id="lossBody" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8F0F24" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#8F0F24" stopOpacity={0.03} />
          </linearGradient>
          <linearGradient id="lossTail" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#B45309" stopOpacity={0.55} />
            <stop offset="100%" stopColor="#B45309" stopOpacity={0.06} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="x"
          type="number"
          domain={[0, "dataMax"]}
          tickFormatter={(v) => moneyCompact(v)}
          tick={{ fontSize: 11, fill: "#6B625E", fontFamily: "var(--font-geist-mono)" }}
          tickLine={false}
          axisLine={{ stroke: "#EAE6E3" }}
          tickCount={5}
        />
        <YAxis hide domain={[0, 1.1]} />
        <Area type="stepAfter" dataKey="body" stroke="#8F0F24" strokeWidth={1.5} fill="url(#lossBody)" isAnimationActive={false} connectNulls={false} />
        <Area type="stepAfter" dataKey="tail" stroke="#B45309" strokeWidth={1.5} fill="url(#lossTail)" isAnimationActive={false} connectNulls={false} />
        <ReferenceLine x={p95} stroke="#B45309" strokeWidth={1.5} label={{ value: "P95", position: "top", fontSize: 10, fill: "#B45309", fontFamily: "var(--font-geist-mono)" }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

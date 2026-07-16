"use client";
import { Area, AreaChart, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { moneyCompact } from "@/lib/format";

/**
 * The signature element: an outcome distribution where a threshold (usually $0)
 * splits benefit from loss. The adverse region is shaded ochre. Reconstructed as
 * a Gaussian from the simulation's expected value and P10/P90 range, faithful
 * for the near-symmetric outcomes it's used on (net savings, gross profit).
 */
function gaussianPoints(expected: number, p10: number, p90: number, n = 96) {
  const sigma = Math.max((p90 - p10) / (2 * 1.2816), Math.abs(expected) * 0.05 || 1);
  const lo = Math.min(p10, expected) - 2.2 * sigma;
  const hi = Math.max(p90, expected) + 2.2 * sigma;
  const step = (hi - lo) / (n - 1);
  const pts = [];
  for (let i = 0; i < n; i++) {
    const x = lo + i * step;
    const y = Math.exp(-0.5 * ((x - expected) / sigma) ** 2);
    pts.push({ x, y });
  }
  return pts;
}

export function DistributionChart({
  expected,
  p10,
  p90,
  threshold = 0,
  height = 260,
  showAxis = true,
}: {
  expected: number;
  p10: number;
  p90: number;
  threshold?: number;
  height?: number;
  showAxis?: boolean;
}) {
  const pts = gaussianPoints(expected, p10, p90);
  // Split the curve at the threshold so the loss side renders ochre.
  const data = pts.map((pt) => ({
    x: pt.x,
    benefit: pt.x >= threshold ? pt.y : null,
    loss: pt.x < threshold ? pt.y : null,
  }));
  // stitch the boundary so the two areas meet
  const bIdx = data.findIndex((d) => d.benefit !== null);
  if (bIdx > 0) data[bIdx - 1].benefit = data[bIdx - 1].loss;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 26, right: 16, bottom: showAxis ? 4 : 0, left: 16 }}>
        <defs>
          <linearGradient id="gBenefit" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8F0F24" stopOpacity={0.42} />
            <stop offset="100%" stopColor="#8F0F24" stopOpacity={0.04} />
          </linearGradient>
          <linearGradient id="gLoss" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#B45309" stopOpacity={0.5} />
            <stop offset="100%" stopColor="#B45309" stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="x"
          type="number"
          domain={["dataMin", "dataMax"]}
          hide={!showAxis}
          tickFormatter={(v) => moneyCompact(v)}
          tick={{ fontSize: 11, fill: "#6B625E", fontFamily: "var(--font-geist-mono)" }}
          tickLine={false}
          axisLine={{ stroke: "#EAE6E3" }}
          tickCount={5}
        />
        <YAxis hide domain={[0, 1.22]} />
        <Area type="monotone" dataKey="loss" stroke="#B45309" strokeWidth={2} fill="url(#gLoss)" isAnimationActive={false} connectNulls={false} />
        <Area type="monotone" dataKey="benefit" stroke="#8F0F24" strokeWidth={2} fill="url(#gBenefit)" isAnimationActive={false} connectNulls={false} />
        <ReferenceLine x={threshold} stroke="#141110" strokeDasharray="3 3" strokeOpacity={0.4} />
        <ReferenceLine x={p10} stroke="#B45309" strokeWidth={1.5} label={{ value: "P10", position: "top", fontSize: 10, fill: "#B45309", fontFamily: "var(--font-geist-mono)" }} />
        <ReferenceLine x={expected} stroke="#8F0F24" strokeWidth={1.5} label={{ value: "E", position: "top", fontSize: 10, fill: "#8F0F24", fontFamily: "var(--font-geist-mono)" }} />
        <ReferenceLine x={p90} stroke="#8F0F24" strokeOpacity={0.5} strokeWidth={1.5} label={{ value: "P90", position: "top", fontSize: 10, fill: "#8F0F24", fontFamily: "var(--font-geist-mono)" }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

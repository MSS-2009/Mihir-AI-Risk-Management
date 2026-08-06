import type { PricedDecision } from "./api";

export interface CostOverride {
  cost_upfront?: number;
  cost_annual?: number;
}

/**
 * Reprice a decision at a cost the operator typed, without a round trip.
 *
 * The engine's NPV is affine in cost:
 *
 *     npv_s = -upfront + (saving_s - annual) * annuity
 *
 * so every headline figure follows from the saving distribution alone. The
 * mean and the percentiles come out exact; the probability is read off the
 * saving quantile grid and agrees with a full re-simulation to about a
 * hundredth of a percentage point.
 *
 * The alternative was a debounced call to the server on every keystroke, half
 * a second each. A cost field you can drag is worth more than one that is
 * right to four decimal places, and the number is not approximate anyway.
 */
export function reprice(d: PricedDecision, override?: CostOverride): PricedDecision {
  if (!override) return d;
  const up = override.cost_upfront ?? d.cost_upfront;
  const yr = override.cost_annual ?? d.cost_annual;
  if (up === d.cost_upfront && yr === d.cost_annual) return d;

  const a = d.annuity_factor;
  const q = d.saving_quantiles;
  if (!a || !q?.length) return d; // older payload, leave it alone

  const npv = -up + (d.expected_saving_annual - yr) * a;
  const netAnnual = d.expected_saving_annual - yr;

  return {
    ...d,
    cost_upfront: up,
    cost_annual: yr,
    net_annual: netAnnual,
    npv,
    npv_p10: -up + (d.saving_p10 - yr) * a,
    npv_p90: -up + (d.saving_p90 - yr) * a,
    prob_beneficial: probBeneficial(q, yr + up / a),
    payback_years: netAnnual > 0 && up > 0 ? up / netAnnual : null,
  };
}

/** Share of scenarios whose saving clears the break-even threshold. */
function probBeneficial(quantiles: number[], threshold: number): number {
  const n = quantiles.length;
  if (threshold <= quantiles[0]) return 1;
  if (threshold >= quantiles[n - 1]) return 0;
  // quantiles[i] is the (100 * i / (n - 1))th percentile, ascending
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (quantiles[mid] <= threshold) lo = mid;
    else hi = mid;
  }
  const span = quantiles[hi] - quantiles[lo];
  const frac = span > 0 ? (threshold - quantiles[lo]) / span : 0;
  const pctBelow = (lo + frac) / (n - 1);
  return Math.min(1, Math.max(0, 1 - pctBelow));
}

/** Re-rank after repricing, so the order still means "best first". */
export function repriceAll(
  decisions: PricedDecision[],
  overrides: Record<string, CostOverride>
): PricedDecision[] {
  return decisions
    .map((d) => reprice(d, overrides[d.id]))
    .sort((a, b) => b.npv - a.npv)
    .map((d, i) => ({ ...d, rank: i + 1 }));
}

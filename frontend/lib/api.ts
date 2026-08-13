/**
 * Where the engine lives.
 *
 * The fallback used to be plain localhost, which is the worst possible default
 * for a deployed page: the site works for whoever happens to be running the
 * backend on their own machine and is silently broken for everyone else. A page
 * served from a real host never falls back to localhost now.
 */
const PRODUCTION_API = "https://avenoir-api.onrender.com";

function resolveApiUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  const servedLocally =
    typeof window === "undefined" ||
    ["localhost", "127.0.0.1", "0.0.0.0"].includes(window.location.hostname);
  if (configured && (servedLocally || !configured.includes("localhost"))) return configured;
  return servedLocally ? "http://localhost:8000" : PRODUCTION_API;
}

const API_URL = resolveApiUrl();

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
  } catch {
    throw new ApiError(
      `Can't reach the analysis engine at ${API_URL}. Start the backend with \`uvicorn main:app --port 8000\`.`,
      0
    );
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(`Request to ${path} failed (${res.status}). ${body}`.trim(), res.status);
  }
  return res.json();
}

// ---- endpoints ----
export const getHealth = () => req<Health>("/");
export const getIndustries = () => req<{ industries: Industry[] }>("/industries");
export const getModels = () => req<ModelsResponse>("/models");
export const getShowcase = () => req<ShowcaseResponse>("/showcase");

export const assess = (body: AssessRequest) =>
  req<Assessment>("/assess", { method: "POST", body: JSON.stringify(body) });

export const assessRobustness = (body: AssessRequest & { eps?: number }) =>
  req<RobustnessResponse>("/assess/robustness", { method: "POST", body: JSON.stringify(body) });

export const analyze = (body: { description?: string; risk_type?: string; params?: Record<string, unknown> }) =>
  req<AnalyzeResponse>("/analyze", { method: "POST", body: JSON.stringify(body) });

// ---- types ----
export interface Health {
  status: string;
  ai_enabled: boolean;
  features: Record<string, boolean>;
  scaffolds: Record<string, boolean>;
  industries: number;
  engines: number;
  n_sims: number;
  n_sims_sweep: number;
}

export interface Question {
  id: string;
  label: string;
  type: "currency" | "percent" | "int" | "number" | "choice" | "text" | "entity_list";
  default: any;
  unit?: string | null;
  help?: string | null;
  choices?: string[] | null;
  fields?: { name: string; label: string; type: string; unit?: string; choices?: string[] }[] | null;
  group?: string | null;
  targets: string[];
  rule?: string | null;
  context_only: boolean;
}

export interface Industry {
  id: string;
  name: string;
  tagline: string;
  reference_revenue: number;
  engines: { engine: string; label: string; description: string; lef: number[]; magnitude: number[] }[];
  questions: Question[];
  correlation: { baseline: number; pairs: { a: string; b: string; rho: number }[] };
  vocabulary: Record<string, string>;
}

export interface AssessRequest {
  industry: string;
  answers?: Record<string, any>;
  correlation_overrides?: Record<string, number>;
  alpha?: number;
  seed?: number;
  /** {decision_id: {cost_upfront, cost_annual}} in the dollars shown on screen. */
  decision_costs?: Record<string, { cost_upfront?: number; cost_annual?: number }>;
  /** "sme" | "midmarket": run against a deterministic fake connected customer. */
  demo_connection?: string | null;
}

export interface DomainContribution {
  domain: string;
  label: string;
  base_share: number;
  tail_share: number;
  expected_annual_loss: number;
}

export interface SensitivityRow {
  engine: string;
  label: string;
  parameter: string;
  parameter_label: string;
  base_p95: number;
  low_p95: number;
  high_p95: number;
  low_delta: number;
  high_delta: number;
  impact: number;
  impact_pct: number;
}

export interface IntakeAdjustment {
  question: string;
  label: string;
  answer: any;
  default: any;
  rule: string;
  rule_description: string;
  engines: string[];
  frequency_multiplier: number;
  magnitude_multiplier: number;
}

export interface Assessment {
  industry: string;
  industry_name: string;
  model: string;
  version: string;
  seed: number;
  method: string;
  n_sims: number;
  expected_annual_loss: number;
  expected_annual_loss_closed_form: number;
  expected_annual_loss_independent: number;
  expected_annual_loss_pct_revenue: number | null;
  exceedance_curve: { percentile: number; loss: number }[];
  exceedance_curve_independent: { percentile: number; loss: number }[];
  correlation_premium: { p95: number; p99: number };
  joint_breach: {
    breach_percentile: number;
    two_plus: number;
    three_plus: number;
    two_plus_independent: number;
    three_plus_independent: number;
  };
  domain_contributions: DomainContribution[];
  sensitivity: SensitivityRow[];
  decisions: PricedDecision[];
  derived_facts: Record<string, any>;
  intake_adjustments: IntakeAdjustment[];
  interpretation: string;
  recommendations: {
    rank: number;
    engine: string;
    domain_label: string;
    title: string;
    expected_annual_exposure: number;
    tail_exposure_p95: number;
    tail_share: number;
    rationale: string;
  }[];
  vocabulary: Record<string, string>;
  /** Present only when the assessment ran against connected data. */
  estimation: Estimation | null;
  assumptions: {
    domains: any[];
    correlation_matrix: { keys: string[]; labels: string[]; matrix: number[][]; repaired: boolean };
    copula: { family: string; df: number; applied_to: string };
    n_sims: number;
    seed: number;
    parameter_basis: string;
    annual_revenue?: number;
    intake_adjustments?: IntakeAdjustment[];
    [k: string]: any;
  };
}

/** Where a parameter's value came from, and how much of it is the customer's. */
export interface ParameterProvenance {
  engine: string;
  parameter: "frequency" | "magnitude" | string;
  provenance: "measured" | "blended" | "prior";
  n_observations: number;
  window_years: number;
  weight_on_data: number;
  credible_interval: [number, number] | null;
  source: string;
  reason: string;
  snapshot_id: string;
  prior_value: number | null;
  value: number | null;
}

export interface Estimation {
  coverage: {
    measured: number;
    blended: number;
    prior: number;
    total: number;
    measured_share: number;
    /** What connecting more would unlock, in the customer's words. */
    unlocks: string[];
  };
  parameters: ParameterProvenance[];
  observations: {
    engine: string;
    n_events: number;
    years_observed: number;
    n_losses: number;
    source: string;
    available: boolean;
    reason: string;
  }[];
  snapshot: {
    snapshot_id: string;
    taken_at: string;
    source: string;
    window_start: string | null;
    window_end: string | null;
    window_years: number;
    completeness: Record<string, string>;
    record_counts: Record<string, number>;
  } | null;
  basis: string;
}

export interface PricedDecision {
  id: string;
  rank: number;
  title: string;
  question: string;
  rationale: string;
  engines: string[];
  effort: string;
  reversible: boolean;
  cost_upfront: number;
  cost_annual: number;
  expected_saving_annual: number;
  saving_p10: number;
  saving_p90: number;
  net_annual: number;
  npv: number;
  npv_p10: number;
  npv_p90: number;
  prob_beneficial: number;
  payback_years: number | null;
  p95_reduction: number;
  p99_reduction: number;
  baseline_expected_loss: number;
  horizon_years: number;
  discount_rate: number;
  /** Present value of $1 a year over the horizon. NPV is affine in cost. */
  annuity_factor: number;
  /** Saving distribution at half-percent steps, so an edited cost repriced
   *  in the browser matches the server rather than approximating it. */
  saving_quantiles: number[];
  cost_editable: boolean;
  basis: string;
}

/** Cached headline figures per industry, for the landing page. */
export interface ShowcaseIndustry {
  id: string;
  name: string;
  tagline: string;
  expected_annual_loss: number;
  pct_revenue: number | null;
  p95: number;
  p99: number;
  reference_revenue: number;
  domains: string[];
  decision: PricedDecision | null;
}

export interface ShowcaseResponse {
  industries: ShowcaseIndustry[];
  n_sims: number;
  seed: number;
  basis: string;
}

export interface FragilityRow {
  pair: string[];
  labels: string[];
  rho: number;
  is_default: boolean;
  p99_swing: number;
}

export interface RobustnessResponse {
  industry: string;
  industry_name: string;
  robustness: {
    eps: number;
    n_draws: number;
    n_sims: number;
    p99_point: number;
    p99_low: number;
    p99_high: number;
    p99_spread_pct: number;
    worst_case_vs_point: number;
    p95_point: number;
    p95_low: number;
    p95_high: number;
    method: string;
  };
  dependence_fragility: FragilityRow[];
  eps_levels: Record<string, number>;
  reading: string;
}

export interface ModelsResponse {
  engines: {
    key: string;
    name: string;
    domain: string;
    version: string;
    method: string;
    description: string;
    modulators: string[];
    parameters: { name: string; label: string; type: string; unit: string }[];
    basis: string;
  }[];
  decision_models: any[];
  modulation_rules: { rule: string; description: string }[];
  settings: {
    n_sims: number;
    n_sims_sweep: number;
    seed: number;
    copula: { family: string; df: number; applied_to: string };
    eps_levels: Record<string, number>;
  };
  parameter_basis: string;
}

export interface AnalyzeResponse {
  risk_type: string;
  model_output: Record<string, any>;
  interpretation: string;
  trace: { model: string; model_key: string; version: string; seed: number; n_sims?: number };
}

// ---- documents (secondary path: optional intake pre-fill) ----
export const getDocumentChecklist = (industry?: string) =>
  req<DocumentsResponse>(`/documents/checklist${industry ? `?industry=${encodeURIComponent(industry)}` : ""}`);

/** The industry decides how a document is read, so it travels with the upload. */
export async function uploadDocuments(files: File[], industry?: string): Promise<DocumentsResponse> {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  if (industry) fd.append("industry", industry);
  let res: Response;
  try {
    res = await fetch(`${API_URL}/documents`, { method: "POST", body: fd });
  } catch {
    throw new ApiError(`Can't reach the analysis engine at ${API_URL}.`, 0);
  }
  if (!res.ok) throw new ApiError(`Upload failed (${res.status}).`, res.status);
  return res.json();
}

export interface ChecklistItem {
  id: string;
  name: string;
  description: string;
  unlocks: string[];
  required: boolean;
  present: boolean;
  status: "present" | "missing" | "optional";
  impact: string | null;
}

export interface DocumentsResponse {
  documents?: {
    filename: string;
    doc_type: string;
    confidence: number;
    extraction: string;
    fields: Record<string, any>;
    note?: string | null;
    chars?: number;
  }[];
  checklist: ChecklistItem[];
  coverage: { required_total: number; required_present: number; pct: number; missing_required: string[] };
  extracted_params?: Record<string, Record<string, unknown>>;
  signals?: {
    signals: { type: string; severity: string; subject: string; message: string; simulated: boolean }[];
    disclaimer: string;
  };
  required_docs?: unknown[];
  ai_enabled?: boolean;
  industry?: string | null;
  /** Rows the documents can fill, keyed by the pack's entity question id. */
  prefill?: Record<string, PrefillTable>;
  /** Tables the documents could not speak to, and why. */
  skipped?: Record<string, string>;
  profile?: string;
  note?: string;
}

export interface PrefillTable {
  label: string;
  rows: Record<string, any>[];
  /** Columns no document evidenced, which kept the pack default. */
  unevidenced: string[];
}

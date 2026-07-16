const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

// ---- Endpoints ----

export function getHealth() {
  return req<HealthResponse>("/");
}

export function getModels() {
  return req<{ models: ModelSpec[] }>("/models");
}

export function getTemplates() {
  return req<TemplatesResponse>("/templates");
}

export function analyze(payload: {
  description?: string;
  risk_type?: string;
  params?: Record<string, unknown>;
}) {
  return req<AnalyzeResponse>("/analyze", { method: "POST", body: JSON.stringify(payload) });
}

export function assess(payload: {
  description?: string;
  domains?: string[];
  params_by_domain?: Record<string, Record<string, unknown>>;
  correlation_overrides?: Record<string, number>;
  output_format?: string;
}) {
  return req<AssessResponse>("/assess", { method: "POST", body: JSON.stringify(payload) });
}

export function getDocumentChecklist() {
  return req<DocumentsResponse>("/documents/checklist");
}

export async function uploadDocuments(files: File[]): Promise<DocumentsResponse> {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  let res: Response;
  try {
    res = await fetch(`${API_URL}/documents`, { method: "POST", body: fd });
  } catch {
    throw new ApiError(`Can't reach the analysis engine at ${API_URL}.`, 0);
  }
  if (!res.ok) throw new ApiError(`Upload failed (${res.status}).`, res.status);
  return res.json();
}

// ---- Types ----

export interface HealthResponse {
  status: string;
  ai_enabled: boolean;
  features: Record<string, boolean>;
  scaffolds: Record<string, boolean>;
  model_count: number;
  output_formats: string[];
}

export interface ParamSpec {
  name: string;
  label: string;
  type: string;
  default: unknown;
  unit?: string | null;
  help?: string | null;
  advanced?: boolean;
  min?: number | null;
  max?: number | null;
  step?: number | null;
  fields?: { name: string; label: string; type: string }[] | null;
  choices?: string[] | null;
}

export interface OutputSpec {
  key: string;
  label: string;
  type: string;
}

export interface ModelSpec {
  key: string;
  name: string;
  version: string;
  domain: string;
  method: string;
  seed: number;
  runnable: boolean;
  docstring: string;
  parameters: ParamSpec[];
  outputs: OutputSpec[];
}

export interface AnalyzeResponse {
  risk_type: string;
  model_output: Record<string, any>;
  interpretation: string;
  trace: { model: string; model_key: string; version: string; seed: number; n_sims?: number };
}

export interface RiskSummary {
  expected_loss: number;
  p95_loss: number;
  std?: number;
  prob_zero_loss?: number;
  quantiles?: Record<string, number>;
  label: string;
}

export interface DomainResult {
  key: string;
  name: string;
  domain: string;
  output: Record<string, any>;
  trace: { model_key: string; version: string; seed: number; n_sims?: number };
}

export interface Composite {
  model: string;
  domains: string[];
  expected_total_loss: number;
  independent_p95: number;
  correlated_p95: number;
  naive_sum_p95: number;
  amplification_pct: number;
  correlated_p99: number;
  headline: string;
  top_pairs: {
    a: string; b: string; a_label: string; b_label: string; rho: number;
    contribution: number; share: number;
  }[];
  correlation_matrix: {
    keys: string[]; labels: string[]; matrix: number[][]; psd_adjusted: boolean;
  };
  insufficient_domains?: boolean;
}

export interface Recommendation {
  rank: number;
  title: string;
  domain: string;
  domain_name: string;
  rationale: string;
  impact_expected: number | null;
  impact_tail: number | null;
}

export interface Delivery {
  format: string;
  view: string;
  title: string;
  headline: string | null;
  key_numbers: { label: string; value: string }[];
  interpretation: string;
  domain_table: { domain: string; expected: string; tail_p95: string }[];
  recommendations: { rank: number; title: string; domain: string; impact: string; rationale: string }[];
  disclaimer: string;
  export: Record<string, { available: boolean; tier: string }>;
}

export interface AssessResponse {
  domains: string[];
  results: Record<string, DomainResult>;
  ranked: DomainResult[];
  composite: Composite | null;
  intake: { domains: string[]; source: string };
  interpretation: string;
  recommendations: Recommendation[];
  delivery: Delivery;
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
}

export interface TemplatesResponse {
  templates: {
    model_key: string;
    name: string;
    version: string;
    runnable: boolean;
    status: string;
    authored_by: string;
    validated_on: string | null;
    backtests: number | null;
    accuracy: Record<string, number> | null;
  }[];
  authoring_pipeline_enabled: boolean;
  note: string;
}

"""Avenoir backend: FastAPI app, routes only.

  engines/     industry-agnostic computation (the numbers)
  industries/  data that parameterizes them (the packs)
  agents/      LangGraph nodes (the LLM selects and interprets, never computes)

Run:  uvicorn main:app --port 8000
"""
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from assessment import run_assessment, run_robustness
from documents import REQUIRED_DOCS, build_checklist, ingest_files, scan_signals
from documents.checklist import coverage, docs_for
from documents.prefill import build_prefill
from engines.constants import DEFAULT_SEED, N_SIMS, N_SIMS_SWEEP
from engines.modulation import RULE_DESCRIPTIONS
from engines.registry import engines_public
from engines.robustness import EPS_LEVELS
from features import features_public
from graph import GRAPH
from industries import INDUSTRY_REGISTRY, industries_public
from llm import ai_enabled
from models import MODEL_REGISTRY
from scaffold import scaffold_status

app = FastAPI(title="Avenoir")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class AssessRequest(BaseModel):
    industry: str
    answers: Optional[dict] = None
    correlation_overrides: Optional[dict] = None
    alpha: float = 1.0
    seed: int = DEFAULT_SEED
    # {decision_id: {"cost_upfront": x, "cost_annual": y}}, in the dollars the
    # operator sees on screen. Sending these back makes an edited run
    # reproducible rather than something that only existed in one browser tab.
    decision_costs: Optional[dict] = None


class RobustnessRequest(AssessRequest):
    eps: float = 0.10


class AnalyzeRequest(BaseModel):
    description: str = ""
    risk_type: Optional[str] = None
    params: Optional[dict] = None


@app.get("/")
def health():
    return {
        "status": "ok",
        "ai_enabled": ai_enabled(),
        "features": features_public(),
        "scaffolds": scaffold_status(),
        "industries": len(INDUSTRY_REGISTRY),
        "engines": len(engines_public()),
        "n_sims": N_SIMS,
        "n_sims_sweep": N_SIMS_SWEEP,
    }


_SHOWCASE: dict | None = None


@app.get("/showcase")
def showcase():
    """Headline figures for every industry, for the landing page.

    Computed once and cached for the life of the process. The landing page must
    show real model output rather than typed-in numbers, but it must not run a
    50,000-scenario simulation for every visitor: on a free-tier dyno that turns
    the front page into the slowest thing we ship.

    The top decision ships with its saving distribution, so the page can reprice
    it against any cost in the browser with no further call.
    """
    global _SHOWCASE
    if _SHOWCASE is not None:
        return _SHOWCASE

    out = []
    for industry, pack in INDUSTRY_REGISTRY.items():
        a = run_assessment(industry, interpret=False, include_sensitivity=False)
        curve = {p["percentile"]: p["loss"] for p in a["exceedance_curve"]}
        top = (a.get("decisions") or [None])[0]
        out.append({
            "id": industry,
            "name": pack.name,
            "tagline": pack.tagline,
            "expected_annual_loss": a["expected_annual_loss"],
            "pct_revenue": a["expected_annual_loss_pct_revenue"],
            "p95": curve.get(95),
            "p99": curve.get(99),
            "reference_revenue": pack.reference_revenue,
            "domains": [d["label"] for d in a["domain_contributions"]],
            "decision": {
                k: top[k] for k in (
                    "id", "title", "question", "cost_upfront", "cost_annual",
                    "expected_saving_annual", "saving_p10", "saving_p90",
                    "npv", "npv_p10", "npv_p90", "prob_beneficial",
                    "annuity_factor", "saving_quantiles", "horizon_years",
                )
            } if top else None,
        })
    _SHOWCASE = {
        "industries": out,
        "n_sims": N_SIMS,
        "seed": DEFAULT_SEED,
        "basis": (
            "Each figure is a seeded run of the published starting calibration for that "
            "industry, at its reference revenue. Your own numbers replace these once you "
            "enter your book."
        ),
    }
    return _SHOWCASE


@app.get("/industries")
def list_industries():
    """The five packs: id, name, engines, questions, defaults, correlation.
    Generated from the registry so intake and the industry cards cannot drift
    from what actually runs."""
    return {"industries": industries_public()}


@app.get("/models")
def list_models():
    """The glass box: every engine, its method, version and parameters, plus the
    published intake modulation rules and the decision models kept alongside."""
    return {
        "engines": engines_public(),
        "decision_models": [s.public() for s in MODEL_REGISTRY.values()],
        "modulation_rules": [
            {"rule": k, "description": v} for k, v in RULE_DESCRIPTIONS.items()
        ],
        "settings": {
            "n_sims": N_SIMS,
            "n_sims_sweep": N_SIMS_SWEEP,
            "seed": DEFAULT_SEED,
            "copula": {"family": "student_t", "df": 4, "applied_to": "magnitude"},
            "eps_levels": EPS_LEVELS,
        },
        "parameter_basis": (
            "Every default is a starting estimate from expert judgment, not measured "
            "loss data. All are editable, and the sensitivity output shows which of "
            "them actually move the answer."
        ),
    }


@app.post("/assess")
def assess(req: AssessRequest):
    """Composite risk for one industry, plus the sensitivity tornado."""
    if req.industry not in INDUSTRY_REGISTRY:
        raise HTTPException(404, f"unknown industry '{req.industry}'")
    return run_assessment(
        req.industry,
        answers=req.answers,
        correlation_overrides=req.correlation_overrides,
        alpha=req.alpha,
        seed=req.seed,
        decision_costs=req.decision_costs,
    )


@app.post("/assess/robustness")
def assess_robustness(req: RobustnessRequest):
    """Dependence-uncertainty layer. Separate endpoint because it runs ~90
    portfolio simulations and would otherwise block the dashboard."""
    if req.industry not in INDUSTRY_REGISTRY:
        raise HTTPException(404, f"unknown industry '{req.industry}'")
    out = run_robustness(
        req.industry,
        answers=req.answers,
        correlation_overrides=req.correlation_overrides,
        alpha=req.alpha,
        eps=req.eps,
        seed=req.seed,
    )
    # Sensitivity and the narrative ride along with the deferred call so the
    # decision view paints fast.
    extra = run_assessment(
        req.industry, answers=req.answers, correlation_overrides=req.correlation_overrides,
        alpha=req.alpha, seed=req.seed, include_sensitivity=True, interpret=True,
        include_decisions=False,
    )
    out["sensitivity"] = extra.get("sensitivity", [])
    out["interpretation"] = extra.get("interpretation", "")
    return out


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """Single decision-model deep dive (tariff reroute, market VaR)."""
    st: dict = {"description": req.description}
    if req.risk_type:
        st["risk_type"] = req.risk_type
    if req.params:
        st["params"] = req.params
    return GRAPH.invoke(st)


@app.get("/documents/checklist")
def documents_checklist(industry: str | None = None):
    """The paperwork THIS industry has. A CRO is asked for protocols and
    enrollment reports, not bills of lading."""
    return {
        "checklist": build_checklist([], industry),
        "coverage": coverage([], industry),
        "required_docs": docs_for(industry),
        "industry": industry,
    }


@app.post("/documents")
async def upload_documents(
    files: list[UploadFile] = File(...),
    industry: str | None = Form(None),
):
    """Optional intake pre-fill, read through the industry's own lens.

    Classification, the fields worth extracting, and the tables they fill all
    come from the industry profile. Extracted values are always returned for the
    user to confirm before anything runs.
    """
    payload = [(f.filename or "upload", await f.read()) for f in files]
    ingested = ingest_files(payload, industry)
    extracts = [{**d["fields"], "doc_type": d["doc_type"]} for d in ingested["documents"]]
    detected = ingested["detected_doc_ids"]
    out = {
        "documents": ingested["documents"],
        "checklist": build_checklist(detected, industry),
        "coverage": coverage(detected, industry),
        "extracted_params": ingested["extracted_params"],
        "signals": scan_signals(extracts),
        "ai_enabled": ai_enabled(),
        "industry": industry,
    }
    if industry and industry in INDUSTRY_REGISTRY:
        out.update(build_prefill(industry, ingested["documents"], INDUSTRY_REGISTRY[industry]))
    return out

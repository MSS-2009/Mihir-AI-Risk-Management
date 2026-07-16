"""Avenoir backend, FastAPI app, routes only.

The heavy lifting lives in:
  models/   validated, seeded simulation library (the numbers)
  agents/   LangGraph nodes (the LLM selects + interprets, never computes)
  graph.py  the assembled agent graph

Run:  uvicorn main:app --reload --port 8000
"""
from typing import Optional

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from assessment import run_full_assessment
from documents import REQUIRED_DOCS, build_checklist, ingest_files, scan_signals
from documents.checklist import coverage
from domains import DEFAULT_DOMAINS, VALID_OUTPUT_FORMATS
from features import features_public
from graph import GRAPH
from llm import ai_enabled
from models import MODEL_REGISTRY
from scaffold import scaffold_status
from templates import templates_public

app = FastAPI(title="Avenoir")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class AnalyzeRequest(BaseModel):
    description: str = ""
    risk_type: Optional[str] = None
    params: Optional[dict] = None


class AssessRequest(BaseModel):
    description: str = ""
    domains: Optional[list[str]] = None
    params_by_domain: Optional[dict] = None
    correlation_overrides: Optional[dict] = None
    output_format: str = "executive_summary"


@app.get("/")
def health():
    return {
        "status": "ok",
        "ai_enabled": ai_enabled(),
        "features": features_public(),
        "scaffolds": scaffold_status(),
        "model_count": len(MODEL_REGISTRY),
        "output_formats": VALID_OUTPUT_FORMATS,
    }


@app.get("/models")
def list_models():
    """The glass box, every model, its method, version, params, assumptions.
    Generated from the registry so it can never drift from the code."""
    return {"models": [spec.public() for spec in MODEL_REGISTRY.values()]}


@app.get("/templates")
def list_templates():
    """Template + accuracy registry (the moat) merged with the live model set."""
    return templates_public()


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    st: dict = {"description": req.description}
    if req.risk_type:
        st["risk_type"] = req.risk_type
    if req.params:
        st["params"] = req.params
    return GRAPH.invoke(st)


@app.get("/documents/checklist")
def documents_checklist():
    """The expected trade-document set and what each one unlocks (empty state)."""
    return {"checklist": build_checklist([]), "coverage": coverage([]), "required_docs": REQUIRED_DOCS}


@app.post("/documents")
async def upload_documents(files: list[UploadFile] = File(...)):
    """Ingest uploaded documents: extract fields, audit completeness, scan
    qualitative signals. Extracted values are returned for the user to confirm
    before any analysis runs."""
    payload = [(f.filename or "upload", await f.read()) for f in files]
    ingested = ingest_files(payload)
    extracts = [
        {**d["fields"], "doc_type": d["doc_type"]} for d in ingested["documents"]
    ]
    detected = ingested["detected_doc_ids"]
    return {
        "documents": ingested["documents"],
        "checklist": build_checklist(detected),
        "coverage": coverage(detected),
        "extracted_params": ingested["extracted_params"],
        "signals": scan_signals(extracts),
        "ai_enabled": ai_enabled(),
    }


@app.post("/assess")
def assess(req: AssessRequest):
    """Full multi-domain assessment: intake -> models -> composite -> interpretation
    -> recommendations -> delivery. Powers the dashboard."""
    return run_full_assessment(
        description=req.description,
        domains=req.domains,
        params_by_domain=req.params_by_domain,
        correlation_overrides=req.correlation_overrides,
        output_format=req.output_format,
    )

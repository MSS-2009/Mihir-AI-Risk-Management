"""Multi-domain assessment orchestration, powers /assess and the dashboard.

Pipeline (the agent nodes, run in sequence):
    intake -> modeling -> correlation -> interpretation -> recommendation -> delivery

Modeling runs concurrently (CPU-bound numpy). Every step degrades gracefully
without an API key. The single-domain LangGraph in graph.py stays as the /analyze
spine; this orchestrator is the multi-domain path.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from agents.delivery import build_delivery
from agents.intake import extract_intent
from agents.interpretation import portfolio_interpretation
from agents.recommendation import build_recommendations
from domains import DEFAULT_DOMAINS, LOSS_DOMAINS  # noqa: F401 (re-exported)
from models import MODEL_REGISTRY, composite_risk_correlation, run, trace_for


def _run_one(key: str, params: dict | None):
    out = run(key, params)
    return key, {
        "key": key,
        "name": MODEL_REGISTRY[key].name,
        "domain": MODEL_REGISTRY[key].domain,
        "output": out,
        "trace": trace_for(key, out),
    }


def _model_and_correlate(domains, params_by_domain, correlation_overrides):
    """The modeling + correlation core (shared, deterministic, no LLM)."""
    domains = [d for d in domains if d in MODEL_REGISTRY and MODEL_REGISTRY[d].runnable]
    params_by_domain = params_by_domain or {}

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(domains) or 1)) as ex:
        futures = [ex.submit(_run_one, d, params_by_domain.get(d)) for d in domains]
        for f in futures:
            key, payload = f.result()
            results[key] = payload

    summaries = {
        k: v["output"]["risk_summary"]
        for k, v in results.items()
        if "risk_summary" in v["output"]
    }
    composite = None
    if len(summaries) >= 2:
        composite = composite_risk_correlation(summaries, correlation_overrides=correlation_overrides)

    ranked = sorted(
        results.values(),
        key=lambda r: r["output"].get("risk_summary", {}).get("p95_loss", 0),
        reverse=True,
    )
    return {
        "domains": [r["key"] for r in ranked],
        "results": {r["key"]: r for r in ranked},
        "ranked": ranked,
        "composite": composite,
    }


def run_assessment(
    domains: list[str] | None = None,
    params_by_domain: dict | None = None,
    correlation_overrides: dict | None = None,
):
    """Modeling + correlation only (used by tests and as the core of a full run)."""
    return _model_and_correlate(domains or DEFAULT_DOMAINS, params_by_domain, correlation_overrides)


def run_full_assessment(
    description: str = "",
    domains: list[str] | None = None,
    params_by_domain: dict | None = None,
    correlation_overrides: dict | None = None,
    output_format: str = "executive_summary",
):
    """The complete pipeline: intake -> models -> composite -> interpretation ->
    recommendations -> delivery. Powers /assess."""
    intent = extract_intent(description, requested_domains=domains)
    merged_params = dict(intent.get("params_by_domain") or {})
    for k, v in (params_by_domain or {}).items():  # explicit params win
        merged_params.setdefault(k, {})
        merged_params[k].update(v)

    core = _model_and_correlate(intent["domains"], merged_params, correlation_overrides)
    interpretation = portfolio_interpretation(core)
    recommendations = build_recommendations(core)
    delivery = build_delivery(core, interpretation, recommendations, output_format)

    return {
        **core,
        "intake": {"domains": intent["domains"], "source": intent.get("source")},
        "interpretation": interpretation,
        "recommendations": recommendations,
        "delivery": delivery,
    }

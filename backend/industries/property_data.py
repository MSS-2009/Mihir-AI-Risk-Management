"""Property & Data Analytics pack. Reference revenue $80M.

A deep pack. The operator enters the upstream feeds their product runs on, the
models they ship, the clients who pay for them and where their records legally
sit, and the parameters are DERIVED from those.

The move that matters here is on model error. "How accurate is your model" is
the wrong question, because the same error rate means two different things
depending on whether a human reviews the output before anyone acts on it. So
the pack asks for volume, error rate and usage separately, and weights them:
a score acted on automatically carries roughly three times the exposure of the
same score used as advisory.

Parameters are starting estimates from expert judgment, not measured loss data.
"""
from engines.decisions import Decision, Intervention
from engines.modulation import Modulation

from .base import EngineBinding, IndustryPack, Question
from .derive import Derivation, centered, derive_all_property, response
from .reference import DECISION_AUTOMATION, PRIVACY_DISCLAIMER, PRIVACY_REGIMES

# The business the published calibration describes. A data business whose own
# book matches these gets the pack default back unchanged.
REF_UNPROTECTED_SHARE = 0.59
REF_TOP_SOURCE_SHARE = 0.41
REF_ERROR_RATE = 0.042
REF_AUTOMATION = 1.34
REF_WRONG_DECISIONS = 15_970.0
REF_CLIENT_HHI = 0.25
REF_RENEWING_SHARE = 0.64
REF_COST_PER_RECORD = 218.0
REF_REG_SEVERITY = 1.24
REF_RECORDS = 2_000_000.0

DEFAULT_SOURCES = [
    {"name": "County deed and assessor feed", "provider": "Ardent Records",
     "criticality": "Core", "has_fallback": False, "annual_cost": 1_450_000},
    {"name": "MLS listing feed", "provider": "Northline Data",
     "criticality": "Core", "has_fallback": True, "annual_cost": 980_000},
    {"name": "Mortgage and lien records", "provider": "Ardent Records",
     "criticality": "Core", "has_fallback": False, "annual_cost": 620_000},
    {"name": "Geospatial and parcel boundaries", "provider": "Terrafix",
     "criticality": "Important", "has_fallback": True, "annual_cost": 310_000},
    {"name": "Permit and inspection records", "provider": "CivicStream",
     "criticality": "Nice to have", "has_fallback": False, "annual_cost": 140_000},
]

DEFAULT_MODELS = [
    {"name": "Automated valuation model", "decisions_per_month": 240_000,
     "usage": "Acted on automatically", "error_rate": 0.045},
    {"name": "Rental yield forecast", "decisions_per_month": 90_000,
     "usage": "Reviewed before use", "error_rate": 0.038},
    {"name": "Portfolio risk score", "decisions_per_month": 50_000,
     "usage": "Advisory only", "error_rate": 0.035},
]

DEFAULT_CLIENTS = [
    {"name": "Kestrel Mortgage", "annual_value": 9_600_000, "months_to_renewal": 7},
    {"name": "Bellhaven Capital", "annual_value": 6_200_000, "months_to_renewal": 19},
    {"name": "Union Title Group", "annual_value": 4_800_000, "months_to_renewal": 4},
    {"name": "Pinnacle REIT", "annual_value": 3_100_000, "months_to_renewal": 26},
    {"name": "Harbourline Lending", "annual_value": 2_400_000, "months_to_renewal": 11},
]

DEFAULT_HOLDINGS = [
    {"jurisdiction": "California", "records": 620_000},
    {"jurisdiction": "US general", "records": 840_000},
    {"jurisdiction": "New York", "records": 310_000},
    {"jurisdiction": "Illinois", "records": 130_000},
    {"jurisdiction": "EU or UK", "records": 100_000},
]


def derive_property(answers: dict, marginals: list) -> tuple[dict, list[dict]]:
    """Turn the feed list, model portfolio, client book and data map into parameters."""
    facts = derive_all_property(answers)
    if not facts:
        return {}, []

    d = Derivation()

    # A core feed with no fallback is the thing that takes the product down.
    if facts.get("unprotected_source_share") is not None:
        s = facts["unprotected_source_share"]
        d.add(
            "third_party_failure",
            Modulation(
                frequency=centered(s, REF_UNPROTECTED_SHARE, 0.50),
                magnitude=centered(s, REF_UNPROTECTED_SHARE, 0.80),
            ),
            "Core feeds running without a fallback",
            f"{facts['unprotected_source_count']} of {facts['core_source_count']} core sources "
            f"have no fallback, {s:.0%} of feed cost"
            + (f": {', '.join(str(x) for x in facts['unprotected_sources'])}"
               if facts.get("unprotected_sources") else ""),
        )
    if facts.get("top_source_share"):
        d.add(
            "third_party_failure",
            Modulation(magnitude=response(facts["top_source_share"], REF_TOP_SOURCE_SHARE, 0.50)),
            "Dependency is concentrated in one feed",
            f"{facts['top_source']} is {facts['top_source_share']:.0%} of feed cost and "
            + ("has a fallback" if facts.get("top_source_has_fallback") else "has none"),
        )

    # Model error: volume times error rate, weighted by whether anyone checks.
    if facts.get("wrong_decisions_per_month"):
        d.add(
            "model_error",
            Modulation(
                frequency=response(facts["wrong_decisions_per_month"], REF_WRONG_DECISIONS, 0.45),
            ),
            "How much wrong output you ship a month",
            f"{facts['wrong_decisions_per_month']:,.0f} of "
            f"{facts['decisions_per_month']:,.0f} monthly decisions at a weighted "
            f"{facts['weighted_error_rate']:.1%} error rate",
        )
    if facts.get("weighted_automation"):
        d.add(
            "model_error",
            Modulation(magnitude=response(facts["weighted_automation"], REF_AUTOMATION, 0.80)),
            "What customers do with the output before anyone checks it",
            f"volume-weighted automation {facts['weighted_automation']:.2f}x"
            + (f"; acted on automatically: {', '.join(str(m) for m in facts['automated_models'])}"
               if facts.get("automated_models") else ""),
        )

    # Client concentration and how much of it is up for renewal.
    if facts.get("client_hhi"):
        d.add(
            "counterparty_concentration",
            Modulation(
                frequency=response(facts["client_hhi"], REF_CLIENT_HHI, 0.30),
                magnitude=response(facts["client_hhi"], REF_CLIENT_HHI, 0.65),
            ),
            "Revenue is concentrated in few clients",
            f"{facts['top_client']} is {facts['top_client_share']:.0%} of contract value; "
            f"effective client count {facts['effective_clients']}",
        )
    if facts.get("renewing_value_share"):
        d.add(
            "counterparty_concentration",
            Modulation(frequency=centered(facts["renewing_value_share"], REF_RENEWING_SHARE, 0.40)),
            "Contract value up for renewal inside a year",
            f"{facts['renewing_within_year']} contracts, "
            f"{facts['renewing_value_share']:.0%} of value",
        )

    # Breach exposure from where the records legally sit.
    if facts.get("records_held"):
        d.add(
            "cyber_loss",
            Modulation(magnitude=response(facts["records_held"], REF_RECORDS, 0.60)),
            f"Records held against a {REF_RECORDS:,.0f} reference",
            f"{facts['records_held']:,.0f} records across "
            f"{facts['jurisdiction_count']} jurisdictions",
        )
    if facts.get("blended_cost_per_record"):
        d.add(
            "cyber_loss",
            Modulation(magnitude=response(facts["blended_cost_per_record"], REF_COST_PER_RECORD, 0.70)),
            "What a record costs to handle where yours actually sit",
            f"blended ${facts['blended_cost_per_record']:,.0f} per record, largest holding in "
            f"{facts['top_jurisdiction']}",
        )
    if facts.get("blended_regulatory_severity"):
        d.add(
            "regulatory_compliance_failure",
            Modulation(
                frequency=response(facts["blended_regulatory_severity"], REF_REG_SEVERITY, 0.50),
                magnitude=response(facts["blended_regulatory_severity"], REF_REG_SEVERITY, 0.70),
            ),
            "The regimes your records sit under",
            f"blended severity {facts['blended_regulatory_severity']:.2f}x, weighted by records "
            f"per jurisdiction",
        )

    return d.result(facts)


PACK = IndustryPack(
    id="property_data",
    name="Property & Data Analytics",
    tagline="Data breach, model accuracy, vendor and API outage, licensing compliance.",
    reference_revenue=80_000_000,
    derive=derive_property,
    bindings=[
        EngineBinding(
            "cyber_loss", "Data breach", (0.08, 0.20, 0.60), (500_000, 4_000_000),
            "A breach exposes the data you hold or license.",
        ),
        EngineBinding(
            "model_error", "Model accuracy failure", (0.15, 0.40, 1.00), (200_000, 1_200_000),
            "A materially wrong valuation or score reaches a customer and gets acted on.",
        ),
        EngineBinding(
            "third_party_failure", "Vendor or API outage", (0.30, 0.80, 2.00), (100_000, 500_000),
            "An upstream data source or API you depend on stops serving.",
        ),
        EngineBinding(
            "regulatory_compliance_failure", "Licensing compliance failure", (0.05, 0.15, 0.50), (300_000, 2_000_000),
            "A data licensing or privacy obligation is breached.",
        ),
        EngineBinding(
            "counterparty_concentration", "Major client loss", (0.10, 0.25, 0.70), (600_000, 2_500_000),
            "A large client does not renew or materially reduces scope.",
        ),
    ],
    correlation_pairs={
        ("cyber_loss", "regulatory_compliance_failure"): 0.55,
        ("cyber_loss", "counterparty_concentration"): 0.45,
        ("model_error", "counterparty_concentration"): 0.40,
        ("regulatory_compliance_failure", "counterparty_concentration"): 0.40,
    },
    questions=[
        Question("annual_revenue", "Annual revenue", "currency", 80_000_000, unit="USD",
                 group="Business",
                 help="Scales every loss magnitude. Frequencies stay flat with size.",
                 targets=["*"], rule="revenue_scale"),

        Question("data_sources", "Upstream data sources", "entity_list", DEFAULT_SOURCES,
                 group="Supply",
                 help="A source marked Core with no fallback is what takes your product down. "
                      "We count those rather than asking how many dependencies you have.",
                 fields=[
                     {"name": "name", "label": "Source", "type": "text"},
                     {"name": "provider", "label": "Provider", "type": "text"},
                     {"name": "criticality", "label": "Criticality", "type": "choice",
                      "choices": ["Core", "Important", "Nice to have"]},
                     {"name": "annual_cost", "label": "Annual cost", "type": "currency"},
                     {"name": "has_fallback", "label": "Has fallback", "type": "bool"},
                 ],
                 targets=["third_party_failure"], rule="derived"),

        Question("models", "Models you ship", "entity_list", DEFAULT_MODELS,
                 group="Product",
                 help="The same error rate means different things depending on whether a human "
                      "reviews the output, so we weight volume and accuracy by how it is used.",
                 fields=[
                     {"name": "name", "label": "Model", "type": "text"},
                     {"name": "decisions_per_month", "label": "Decisions per month", "type": "int"},
                     {"name": "usage", "label": "How customers use it", "type": "choice",
                      "choices": list(DECISION_AUTOMATION.keys())},
                     {"name": "error_rate", "label": "Material error rate", "type": "percent"},
                 ],
                 targets=["model_error"], rule="derived"),

        Question("clients", "Client contracts", "entity_list", DEFAULT_CLIENTS,
                 group="Revenue",
                 help="Concentration and renewal exposure are computed from this, so you do not "
                      "have to work out your own largest-client percentage.",
                 fields=[
                     {"name": "name", "label": "Client", "type": "text"},
                     {"name": "annual_value", "label": "Annual value", "type": "currency"},
                     {"name": "months_to_renewal", "label": "Months to renewal", "type": "int"},
                 ],
                 targets=["counterparty_concentration"], rule="derived"),

        Question("data_holdings", "Where your records sit", "entity_list", DEFAULT_HOLDINGS,
                 group="Data estate",
                 help="Per-record response cost and regulatory severity differ by jurisdiction. "
                      "We blend them by how many records sit in each.",
                 fields=[
                     {"name": "jurisdiction", "label": "Jurisdiction", "type": "choice",
                      "choices": list(PRIVACY_REGIMES.keys())},
                     {"name": "records", "label": "Records", "type": "int"},
                 ],
                 targets=["cyber_loss", "regulatory_compliance_failure"], rule="derived"),

        Question("privacy_maturity", "Privacy and security control maturity", "choice", "Defined",
                 group="Controls",
                 choices=["Initial", "Developing", "Defined", "Managed", "Optimizing"],
                 help="Stronger controls lower how often an incident becomes a loss event.",
                 targets=["cyber_loss"], rule="control_maturity"),

        Question("model_validation", "Model validation practice", "choice", "Periodic",
                 group="Controls",
                 choices=["Ad hoc", "Periodic", "Continuous with holdout", "Independently reviewed"],
                 help="Validation catches wrong output before a customer acts on it.",
                 targets=["model_error"], rule="validation_maturity"),

        Question("license_complexity", "Data licensing obligations", "choice", "Moderate",
                 group="Controls",
                 choices=["Simple", "Moderate", "Complex", "Highly restrictive"],
                 help="More restrictive terms create more ways to breach them.",
                 targets=["regulatory_compliance_failure"], rule="process_maturity_inverse"),
    ],
    decisions=[
        Decision(
            id="continuous_validation",
            title="Move validation to continuous with a holdout set",
            question="Should we validate continuously instead of periodically?",
            rationale=(
                "You ship about {wrong_decisions_per_month_int} materially wrong decisions a "
                "month, and {top_model} is acted on without review. Validation is what catches "
                "that before a customer relies on it."
            ),
            interventions=[Intervention("model_error", frequency=0.55, magnitude=0.75)],
            cost_upfront=0, cost_annual=210_000, effort="moderate",
        ),
        Decision(
            id="redundant_sources",
            title="Add a fallback for {top_source}",
            question="Should we pay for a redundant feed on our most critical source?",
            rationale=(
                "{unprotected_source_count_int} core sources run with no fallback, "
                "{unprotected_source_share_pct} of your feed spend. An upstream outage stops "
                "your product; a fallback does not prevent their outage, it prevents yours."
            ),
            interventions=[Intervention("third_party_failure", magnitude=0.45)],
            cost_upfront=60_000, cost_annual=165_000, effort="moderate",
        ),
        Decision(
            id="privacy_uplift",
            title="Advance privacy and security controls one level",
            question="Should we fund the next step of the security roadmap?",
            rationale=(
                "You hold {records_held_int} records at a blended "
                "{blended_cost_per_record_money} each to handle, concentrated in "
                "{top_jurisdiction}. Stronger controls lower how often that becomes a "
                "reportable loss."
            ),
            interventions=[
                Intervention("cyber_loss", frequency=0.60),
                Intervention("regulatory_compliance_failure", frequency=0.80),
            ],
            cost_upfront=120_000, cost_annual=190_000, effort="moderate",
        ),
        Decision(
            id="diversify_clients",
            title="Reduce revenue concentration in {top_client}",
            question="Should we invest in winning mid-size accounts?",
            rationale=(
                "{top_client} is {top_client_share_pct} of contract value and "
                "{renewing_value_share_pct} of your book renews inside a year. "
                "Concentration means one renewal conversation decides your year."
            ),
            interventions=[Intervention("counterparty_concentration", magnitude=0.65)],
            cost_upfront=0, cost_annual=280_000, effort="high",
        ),
        Decision(
            id="human_review_gate",
            title="Put a review gate on automatically actioned output",
            question="Should high-impact scores be reviewed before a customer acts?",
            rationale=(
                "Output acted on automatically carries roughly three times the exposure of the "
                "same output used as advisory. A gate on the highest-impact slice buys most of "
                "that back without slowing the rest."
            ),
            interventions=[Intervention("model_error", magnitude=0.60)],
            cost_upfront=45_000, cost_annual=155_000, effort="low",
        ),
    ],
    vocabulary={
        "counterparty": "client",
        "third_party": "data vendor",
        "privacy_disclaimer": PRIVACY_DISCLAIMER,
    },
)

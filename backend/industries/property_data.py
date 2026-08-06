"""Property & Data Analytics pack. Reference revenue $80M.

Parameters are starting estimates from expert judgment, not measured loss data.
"""
from engines.decisions import Decision, Intervention

from .base import EngineBinding, IndustryPack, Question

PACK = IndustryPack(
    id="property_data",
    name="Property & Data Analytics",
    tagline="Data breach, model accuracy, vendor and API outage, licensing compliance.",
    reference_revenue=80_000_000,
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
                 help="Scales every loss magnitude. Frequencies stay flat with size.",
                 targets=["*"], rule="revenue_scale"),
        Question("records_held", "Sensitive records held", "int", 2_000_000,
                 help="More records held, larger breach magnitude.",
                 targets=["cyber_loss"], rule="records_held"),
        Question("privacy_maturity", "Privacy and security control maturity", "choice", "Defined",
                 choices=["Initial", "Developing", "Defined", "Managed", "Optimizing"],
                 help="Stronger controls lower how often an incident becomes a loss event.",
                 targets=["cyber_loss"], rule="control_maturity"),
        Question("model_validation", "Model validation practice", "choice", "Periodic",
                 choices=["Ad hoc", "Periodic", "Continuous with holdout", "Independently reviewed"],
                 help="Validation catches wrong output before a customer acts on it.",
                 targets=["model_error"], rule="validation_maturity"),
        Question("external_data_sources", "Number of external data sources you depend on", "int", 6,
                 help="More upstream dependencies, more outage exposure.",
                 targets=["third_party_failure"], rule="site_count_inverse"),
        Question("top_client_share", "Share of revenue from your largest client", "percent", 0.22,
                 help="Concentration raises both the odds and the cost of a client loss.",
                 targets=["counterparty_concentration"], rule="concentration"),
        Question("license_complexity", "Data licensing obligations", "choice", "Moderate",
                 choices=["Simple", "Moderate", "Complex", "Highly restrictive"],
                 help="More restrictive terms create more ways to breach them.",
                 targets=["regulatory_compliance_failure"], rule="process_maturity_inverse"),
    ],
    decisions=[
        Decision(
            id="continuous_validation",
            title="Move model validation to continuous with a holdout set",
            question="Should we validate continuously instead of periodically?",
            rationale=(
                "Validation is what catches a wrong output before a customer acts on "
                "it. It cuts how often bad output ships and how far it gets."
            ),
            interventions=[Intervention("model_error", frequency=0.55, magnitude=0.75)],
            cost_upfront=0, cost_annual=210_000, effort="moderate",
        ),
        Decision(
            id="redundant_sources",
            title="Add a fallback for your most critical upstream source",
            question="Should we pay for a redundant data feed?",
            rationale=(
                "An upstream outage stops your product. A fallback does not prevent "
                "their outage, it prevents yours."
            ),
            interventions=[Intervention("third_party_failure", magnitude=0.45)],
            cost_upfront=60_000, cost_annual=165_000, effort="moderate",
        ),
        Decision(
            id="privacy_uplift",
            title="Advance privacy and security controls one level",
            question="Should we fund the next step of the security roadmap?",
            rationale=(
                "Stronger controls lower how often an incident becomes a reportable "
                "loss. They also reduce the compliance exposure that follows one."
            ),
            interventions=[
                Intervention("cyber_loss", frequency=0.60),
                Intervention("regulatory_compliance_failure", frequency=0.80),
            ],
            cost_upfront=120_000, cost_annual=190_000, effort="moderate",
        ),
        Decision(
            id="diversify_clients",
            title="Reduce revenue concentration in your largest client",
            question="Should we invest in winning mid-size accounts?",
            rationale=(
                "Concentration means one renewal conversation decides your year. "
                "Spreading it lowers what any single loss costs."
            ),
            interventions=[Intervention("counterparty_concentration", magnitude=0.65)],
            cost_upfront=0, cost_annual=280_000, effort="high",
        ),
    ],
    vocabulary={"counterparty": "client", "third_party": "data vendor"},
)

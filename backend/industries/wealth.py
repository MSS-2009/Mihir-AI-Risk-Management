"""Wealth Management & Finance pack. Reference revenue $40M.

Parameters are starting estimates from expert judgment, not measured loss data.
As with clinical, this is a regulated setting: nothing in this pack should be
presented as an empirical benchmark, because it is not one.
"""
from engines.decisions import Decision, Intervention

from .base import EngineBinding, IndustryPack, Question

PACK = IndustryPack(
    id="wealth_management",
    name="Wealth Management & Finance",
    tagline="Client data incident, compliance failure, client attrition, reputational event.",
    reference_revenue=40_000_000,
    bindings=[
        EngineBinding(
            "cyber_loss", "Client data incident", (0.06, 0.15, 0.45), (300_000, 2_500_000),
            "An incident exposes client financial or identity data.",
        ),
        EngineBinding(
            "regulatory_compliance_failure", "Compliance failure", (0.07, 0.18, 0.50), (250_000, 1_700_000),
            "A suitability, disclosure or documentation failure requires remediation.",
        ),
        EngineBinding(
            "counterparty_concentration", "Client attrition under stress", (0.15, 0.40, 1.00), (220_000, 1_100_000),
            "Clients leave following a market drawdown or a service failure.",
        ),
        EngineBinding(
            "reputational_event", "Reputational event", (0.03, 0.09, 0.30), (350_000, 2_200_000),
            "An incident damages standing with clients and referral sources.",
        ),
        EngineBinding(
            "third_party_failure", "Vendor outage", (0.25, 0.60, 1.50), (80_000, 400_000),
            "A custodian, planning or reporting platform you depend on goes down.",
        ),
    ],
    correlation_pairs={
        ("cyber_loss", "regulatory_compliance_failure"): 0.45,
        ("cyber_loss", "reputational_event"): 0.55,
        ("regulatory_compliance_failure", "reputational_event"): 0.50,
        ("counterparty_concentration", "reputational_event"): 0.50,
    },
    questions=[
        Question("annual_revenue", "Annual revenue", "currency", 40_000_000, unit="USD",
                 help="Scales every loss magnitude. Frequencies stay flat with size.",
                 targets=["*"], rule="revenue_scale"),
        Question("client_records", "Client records held", "int", 12_000,
                 help="More records held, larger incident magnitude.",
                 targets=["cyber_loss"], rule="records_held"),
        Question("cyber_controls", "Cyber control maturity", "choice", "Defined",
                 choices=["Initial", "Developing", "Defined", "Managed", "Optimizing"],
                 help="Stronger controls lower how often an incident becomes a loss event.",
                 targets=["cyber_loss"], rule="control_maturity"),
        Question("compliance_process", "Compliance review process", "choice", "Periodic",
                 choices=["Ad hoc", "Periodic", "Systematic", "Independently audited"],
                 help="A systematic process catches failures before they become findings.",
                 targets=["regulatory_compliance_failure"], rule="process_maturity"),
        Question("advisor_documentation", "Advice documentation practice", "choice", "Standardised",
                 choices=["Inconsistent", "Standardised", "Reviewed", "Systematically audited"],
                 help="Documentation is the primary defence when advice is challenged.",
                 targets=["regulatory_compliance_failure", "reputational_event"], rule="process_maturity"),
        Question("top_client_share", "Share of revenue from your largest client", "percent", 0.12,
                 help="Concentration raises both the odds and the cost of attrition.",
                 targets=["counterparty_concentration"], rule="concentration"),
        Question("market_beta", "Share of revenue tied to market levels", "percent", 0.70,
                 help="Fee revenue that moves with markets makes attrition costlier in a drawdown.",
                 targets=["counterparty_concentration"], rule="exposure_share"),
        Question("core_vendors", "Number of core platform vendors", "int", 4,
                 help="More platform dependencies, more outage exposure.",
                 targets=["third_party_failure"], rule="site_count_inverse"),
    ],
    decisions=[
        Decision(
            id="systematic_compliance",
            title="Move compliance review from periodic to systematic",
            question="Should we review every file rather than a sample?",
            rationale=(
                "Systematic review catches suitability and disclosure gaps while they "
                "are still fixable, which changes both how often a finding happens and "
                "how large it is."
            ),
            interventions=[
                Intervention("regulatory_compliance_failure", frequency=0.55, magnitude=0.80),
                Intervention("reputational_event", frequency=0.85),
            ],
            cost_upfront=0, cost_annual=195_000, effort="moderate",
        ),
        Decision(
            id="cyber_uplift",
            title="Advance cyber controls one maturity level",
            question="Should we fund the next step of the security roadmap?",
            rationale=(
                "Client financial data is the asset most likely to be attacked and the "
                "one whose loss travels furthest into reputation."
            ),
            interventions=[
                Intervention("cyber_loss", frequency=0.60),
                Intervention("reputational_event", frequency=0.85),
            ],
            cost_upfront=85_000, cost_annual=140_000, effort="moderate",
        ),
        Decision(
            id="documentation_standard",
            title="Standardise and audit advice documentation",
            question="Should we audit how advice is recorded?",
            rationale=(
                "Documentation is the primary defence when advice is challenged. It "
                "does not stop the challenge, it decides how it ends."
            ),
            interventions=[Intervention("regulatory_compliance_failure", magnitude=0.65)],
            cost_upfront=0, cost_annual=110_000, effort="low",
        ),
        Decision(
            id="retention_programme",
            title="Fund a structured client retention programme",
            question="Should we invest in retention ahead of the next drawdown?",
            rationale=(
                "Attrition spikes exactly when markets fall and fee revenue is already "
                "down. Retention work bought in advance is what blunts that."
            ),
            interventions=[Intervention("counterparty_concentration", frequency=0.70, magnitude=0.85)],
            cost_upfront=0, cost_annual=125_000, effort="moderate",
        ),
    ],
    vocabulary={"counterparty": "client", "third_party": "platform vendor"},
)

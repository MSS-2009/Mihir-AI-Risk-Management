"""Wealth Management & Finance pack. Reference revenue $40M.

A deep pack. The operator enters their relationships, their advisors and the
platforms the practice runs on, and the parameters are DERIVED from those.

The move that matters here is key-person risk, which is the risk in this
business and the one nobody models. A wealth manager's book walks out of the
door with the advisor who owns the relationship, so the pack computes AUM
concentration by advisor and, separately, how much of the book sits with
someone retiring inside five years with no named successor. That second number
is usually the largest single exposure in the practice and it never appears on
a risk register.

Fee revenue is derived rather than asked for: AUM times basis points, with the
market-linked share separated out so a drawdown scenario is a calculation
rather than a guess.

Parameters are starting estimates from expert judgment, not measured loss data.
As with clinical, this is a regulated setting: nothing in this pack should be
presented as an empirical benchmark, because it is not one. Nothing here is
investment advice.
"""
from engines.decisions import Decision, Intervention
from engines.modulation import Modulation

from .base import EngineBinding, IndustryPack, Question
from .derive import Derivation, centered, derive_all_wealth, response
from .reference import REGISTRATION_REGIMES, WEALTH_DISCLAIMER

# The practice the published calibration describes. A firm whose own book
# matches these gets the pack default back unchanged.
REF_CLIENT_HHI = 0.25
REF_MARKET_LINKED = 0.67
REF_ADVISOR_HHI = 0.26
REF_UNSUCCESSIONED_SHARE = 0.32
REF_EXAMS_PER_YEAR = 0.25
REF_ENFORCEMENT_SEVERITY = 1.00
REF_NO_FALLBACK_COUNT = 2.0

DEFAULT_RELATIONSHIPS = [
    {"name": "Ashford family office", "aum": 310_000_000, "fee_bps": 65, "market_linked_share": 0.80},
    {"name": "Verity Foundation", "aum": 180_000_000, "fee_bps": 55, "market_linked_share": 0.85},
    {"name": "Lindqvist trust group", "aum": 145_000_000, "fee_bps": 75, "market_linked_share": 0.70},
    {"name": "Private client book, top 50", "aum": 620_000_000, "fee_bps": 95, "market_linked_share": 0.65},
    {"name": "Private client book, remainder", "aum": 410_000_000, "fee_bps": 105, "market_linked_share": 0.60},
]

DEFAULT_ADVISORS = [
    {"name": "M. Okonjo", "book_aum": 540_000_000, "clients": 78,
     "retiring_5y": True, "has_successor": False},
    {"name": "R. Castellanos", "book_aum": 420_000_000, "clients": 112,
     "retiring_5y": False, "has_successor": True},
    {"name": "S. Whitfield", "book_aum": 380_000_000, "clients": 95,
     "retiring_5y": True, "has_successor": True},
    {"name": "J. Ferrara", "book_aum": 325_000_000, "clients": 140,
     "retiring_5y": False, "has_successor": False},
]

DEFAULT_PLATFORMS = [
    {"name": "Schwab custody", "function": "Custodian", "has_fallback": False, "annual_cost": 640_000},
    {"name": "Addepar", "function": "Portfolio accounting", "has_fallback": False, "annual_cost": 410_000},
    {"name": "Salesforce Financial Services", "function": "CRM", "has_fallback": True, "annual_cost": 185_000},
    {"name": "eMoney", "function": "Planning", "has_fallback": True, "annual_cost": 120_000},
]


def derive_wealth(answers: dict, marginals: list) -> tuple[dict, list[dict]]:
    """Turn the client book, advisor roster and platform stack into parameters."""
    facts = derive_all_wealth(answers)
    if not facts:
        return {}, []

    d = Derivation()

    # Client concentration from the relationship book.
    if facts.get("client_hhi"):
        d.add(
            "counterparty_concentration",
            Modulation(
                frequency=response(facts["client_hhi"], REF_CLIENT_HHI, 0.30),
                magnitude=response(facts["client_hhi"], REF_CLIENT_HHI, 0.60),
            ),
            "Fee revenue is concentrated in few relationships",
            f"{facts['top_client']} is {facts['top_client_share']:.0%} of AUM; "
            f"{facts['relationship_count']} relationships at a blended "
            f"{facts['blended_fee_bps']:.0f} bps",
        )

    # Market-linked fee revenue is what makes attrition bite in a drawdown.
    if facts.get("market_linked_share"):
        s = facts["market_linked_share"]
        d.add(
            "counterparty_concentration",
            Modulation(magnitude=centered(s, REF_MARKET_LINKED, 0.60)),
            "Fee revenue that moves with markets",
            f"{s:.0%} of ${facts['fee_revenue']:,.0f} fee revenue is market-linked, about "
            f"${facts['revenue_at_20pct_drawdown']:,.0f} at a 20% drawdown",
        )

    # Key-person risk. The book leaves with the advisor.
    if facts.get("advisor_hhi"):
        d.add(
            "counterparty_concentration",
            Modulation(
                frequency=response(facts["advisor_hhi"], REF_ADVISOR_HHI, 0.35),
                magnitude=response(facts["advisor_hhi"], REF_ADVISOR_HHI, 0.55),
            ),
            "AUM is concentrated in few advisors",
            f"{facts['top_advisor']} holds {facts['top_advisor_share']:.0%} of AUM across "
            f"{facts['advisor_count']} advisors",
        )
    if facts.get("unsuccessioned_aum_share") is not None:
        s = facts["unsuccessioned_aum_share"]
        d.add(
            "counterparty_concentration",
            Modulation(
                frequency=centered(s, REF_UNSUCCESSIONED_SHARE, 0.55),
                magnitude=centered(s, REF_UNSUCCESSIONED_SHARE, 0.70),
            ),
            "Book held by advisors retiring without a successor",
            f"{facts['unsuccessioned_count']} of {facts['retiring_count']} retiring advisors "
            f"have no named successor, {s:.0%} of AUM"
            + (f": {', '.join(str(a) for a in facts['unsuccessioned_advisors'])}"
               if facts.get("unsuccessioned_advisors") else ""),
        )
        d.add(
            "reputational_event",
            Modulation(frequency=centered(s, REF_UNSUCCESSIONED_SHARE, 0.30)),
            "An unplanned advisor departure is visible to clients",
            f"{s:.0%} of AUM has no succession plan",
        )

    # The regime you are examined under.
    if facts.get("exams_per_year"):
        d.add(
            "regulatory_compliance_failure",
            Modulation(frequency=response(facts["exams_per_year"], REF_EXAMS_PER_YEAR, 0.35)),
            "Examination frequency for your registration",
            facts.get("registration_basis", ""),
        )
    if facts.get("enforcement_severity"):
        d.add(
            "regulatory_compliance_failure",
            Modulation(magnitude=response(facts["enforcement_severity"], REF_ENFORCEMENT_SEVERITY, 0.70)),
            "Enforcement severity for your registration",
            f"{facts.get('registration', '')} carries "
            f"{facts['enforcement_severity']:.2f}x the reference severity",
        )

    # Platforms with no fallback.
    if facts.get("no_fallback_count") is not None:
        n = float(facts["no_fallback_count"])
        d.add(
            "third_party_failure",
            Modulation(
                frequency=response(max(n, 0.5), max(REF_NO_FALLBACK_COUNT, 0.5), 0.45),
                magnitude=response(max(n, 0.5), max(REF_NO_FALLBACK_COUNT, 0.5), 0.35),
            ),
            "Platforms running with no fallback",
            f"{facts['no_fallback_count']} of {facts['platform_count']} platforms have none"
            + (f": {', '.join(str(x) for x in facts['no_fallback_platforms'])}"
               if facts.get("no_fallback_platforms") else ""),
        )

    return d.result(facts)


PACK = IndustryPack(
    id="wealth_management",
    name="Wealth Management & Finance",
    tagline="Client data incident, compliance failure, client attrition, reputational event.",
    reference_revenue=40_000_000,
    derive=derive_wealth,
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
            "Clients leave following a market drawdown, an advisor departure or a service failure.",
        ),
        EngineBinding(
            "reputational_event", "Reputational event", (0.03, 0.09, 0.30), (350_000, 2_200_000),
            "An incident damages standing with clients and referral sources.",
        ),
        EngineBinding(
            "third_party_failure", "Platform outage", (0.25, 0.60, 1.50), (80_000, 400_000),
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
                 group="Business",
                 help="Scales every loss magnitude. Frequencies stay flat with size.",
                 targets=["*"], rule="revenue_scale"),

        Question("registration", "Registration", "choice", "RIA (SEC)",
                 group="Business",
                 choices=list(REGISTRATION_REGIMES.keys()),
                 help="Sets examination frequency and enforcement severity from a reference "
                      "table, so you do not have to estimate your own exam cycle.",
                 targets=["regulatory_compliance_failure"], rule="derived"),

        Question("relationships", "Client relationships", "entity_list", DEFAULT_RELATIONSHIPS,
                 group="Client book",
                 help="Fee revenue is AUM times basis points. Concentration and drawdown "
                      "exposure are computed from this rather than asked for.",
                 fields=[
                     {"name": "name", "label": "Relationship", "type": "text"},
                     {"name": "aum", "label": "AUM", "type": "currency"},
                     {"name": "fee_bps", "label": "Fee", "type": "int", "unit": "bps"},
                     {"name": "market_linked_share", "label": "Market-linked", "type": "percent"},
                 ],
                 targets=["counterparty_concentration"], rule="derived"),

        Question("advisors", "Advisors and their books", "entity_list", DEFAULT_ADVISORS,
                 group="Key people",
                 help="The book leaves with the advisor. We compute AUM concentration by "
                      "advisor and, separately, how much sits with someone retiring inside five "
                      "years with no named successor.",
                 fields=[
                     {"name": "name", "label": "Advisor", "type": "text"},
                     {"name": "book_aum", "label": "Book AUM", "type": "currency"},
                     {"name": "clients", "label": "Clients", "type": "int"},
                     {"name": "retiring_5y", "label": "Retiring within 5y", "type": "bool"},
                     {"name": "has_successor", "label": "Named successor", "type": "bool"},
                 ],
                 targets=["counterparty_concentration", "reputational_event"], rule="derived"),

        Question("platforms", "Platforms the practice runs on", "entity_list", DEFAULT_PLATFORMS,
                 group="Operations",
                 help="Custody and portfolio accounting are treated as critical, because an "
                      "outage in either stops you trading and reporting.",
                 fields=[
                     {"name": "name", "label": "Platform", "type": "text"},
                     {"name": "function", "label": "Function", "type": "choice",
                      "choices": ["Custodian", "Portfolio accounting", "CRM", "Planning", "Reporting"]},
                     {"name": "annual_cost", "label": "Annual cost", "type": "currency"},
                     {"name": "has_fallback", "label": "Has fallback", "type": "bool"},
                 ],
                 targets=["third_party_failure"], rule="derived"),

        Question("client_records", "Client records held", "int", 12_000,
                 group="Controls",
                 help="More records held, larger incident magnitude.",
                 targets=["cyber_loss"], rule="records_held"),

        Question("cyber_controls", "Cyber control maturity", "choice", "Defined",
                 group="Controls",
                 choices=["Initial", "Developing", "Defined", "Managed", "Optimizing"],
                 help="Stronger controls lower how often an incident becomes a loss event.",
                 targets=["cyber_loss"], rule="control_maturity"),

        Question("compliance_process", "Compliance review process", "choice", "Periodic",
                 group="Controls",
                 choices=["Ad hoc", "Periodic", "Systematic", "Independently audited"],
                 help="A systematic process catches failures before they become findings.",
                 targets=["regulatory_compliance_failure"], rule="process_maturity"),

        Question("advisor_documentation", "Advice documentation practice", "choice", "Standardised",
                 group="Controls",
                 choices=["Inconsistent", "Standardised", "Reviewed", "Systematically audited"],
                 help="Documentation is the primary defence when advice is challenged.",
                 targets=["regulatory_compliance_failure", "reputational_event"], rule="process_maturity"),
    ],
    decisions=[
        Decision(
            id="succession_plan",
            title="Fund succession and retention for {top_advisor}",
            question="Should we buy out or bind the books with no successor?",
            rationale=(
                "{unsuccessioned_aum_share_pct} of AUM sits with advisors retiring inside five "
                "years and no named successor. That book does not leave gradually, it leaves "
                "with the person, and a retention agreement is cheaper than reacquiring it."
            ),
            interventions=[
                Intervention("counterparty_concentration", frequency=0.60, magnitude=0.70),
                Intervention("reputational_event", frequency=0.85),
            ],
            cost_upfront=340_000, cost_annual=180_000, effort="high",
        ),
        Decision(
            id="systematic_compliance",
            title="Move compliance review from periodic to systematic",
            question="Should we review every file rather than a sample?",
            rationale=(
                "As a {registration} you face about {exams_per_year} examinations a year. "
                "Systematic review catches suitability and disclosure gaps while they are still "
                "fixable, which changes both how often a finding happens and how large it is."
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
                "Client financial data is the asset most likely to be attacked and the one "
                "whose loss travels furthest into reputation."
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
                "Documentation is the primary defence when advice is challenged. It does not "
                "stop the challenge, it decides how it ends."
            ),
            interventions=[Intervention("regulatory_compliance_failure", magnitude=0.65)],
            cost_upfront=0, cost_annual=110_000, effort="low",
        ),
        Decision(
            id="retention_programme",
            title="Fund a structured client retention programme",
            question="Should we invest in retention ahead of the next drawdown?",
            rationale=(
                "{market_linked_share_pct} of fee revenue moves with markets, about "
                "{revenue_at_20pct_drawdown_money} at a 20% drawdown. Attrition spikes exactly "
                "when fee revenue is already down, and retention work has to be bought before "
                "that, not during it."
            ),
            interventions=[Intervention("counterparty_concentration", frequency=0.70, magnitude=0.85)],
            cost_upfront=0, cost_annual=125_000, effort="moderate",
        ),
        Decision(
            id="platform_fallback",
            title="Establish a fallback for {top_platform}",
            question="Should we stand up a secondary path for critical platforms?",
            rationale=(
                "{no_fallback_count_int} platforms run with no fallback. An outage in custody "
                "or portfolio accounting stops you trading and reporting on the same day."
            ),
            interventions=[Intervention("third_party_failure", magnitude=0.50)],
            cost_upfront=70_000, cost_annual=95_000, effort="moderate",
        ),
    ],
    vocabulary={
        "counterparty": "client",
        "third_party": "platform vendor",
        "registration_disclaimer": WEALTH_DISCLAIMER,
    },
)

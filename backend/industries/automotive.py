"""Automotive & Manufacturing pack. Reference revenue $250M.

Parameters are starting estimates from expert judgment, not measured loss data.
"""
from engines.decisions import Decision, Intervention

from .base import EngineBinding, IndustryPack, Question

PACK = IndustryPack(
    id="automotive_manufacturing",
    name="Automotive & Manufacturing",
    tagline="Supplier failure, recall and warranty, production delay, material cost shock.",
    reference_revenue=250_000_000,
    bindings=[
        EngineBinding(
            "third_party_failure", "Supplier failure", (0.20, 0.50, 1.20), (400_000, 1_600_000),
            "A tier-one or single-source supplier cannot deliver to schedule or spec.",
        ),
        EngineBinding(
            "product_recall", "Recall and warranty", (0.05, 0.15, 0.40), (800_000, 6_000_000),
            "A defect triggers a recall campaign or a wave of warranty claims.",
        ),
        EngineBinding(
            "schedule_disruption", "Production delay", (0.40, 1.00, 2.50), (250_000, 1_200_000),
            "A line stops or slips against the build schedule.",
        ),
        EngineBinding(
            "input_cost_shock", "Material cost shock", (0.30, 0.80, 1.60), (500_000, 2_000_000),
            "Steel, resin, electronics or duties move against you on committed volume.",
        ),
        EngineBinding(
            "cyber_loss", "Cyber incident", (0.05, 0.15, 0.50), (300_000, 2_500_000),
            "A security incident interrupts plant systems or exposes design data.",
        ),
    ],
    correlation_pairs={
        ("third_party_failure", "schedule_disruption"): 0.60,
        ("third_party_failure", "input_cost_shock"): 0.45,
        ("product_recall", "schedule_disruption"): 0.40,
        ("cyber_loss", "schedule_disruption"): 0.35,
    },
    questions=[
        Question("annual_revenue", "Annual revenue", "currency", 250_000_000, unit="USD",
                 help="Scales every loss magnitude. Frequencies stay flat with size.",
                 targets=["*"], rule="revenue_scale"),
        Question("top_supplier_share", "Share of parts spend with your largest supplier", "percent", 0.28,
                 help="Concentration raises how often a supplier failure bites and what it costs.",
                 targets=["third_party_failure"], rule="concentration"),
        Question("single_source_parts", "Share of parts that are single-sourced", "percent", 0.20,
                 help="Single-sourced parts have no fallback when a supplier fails.",
                 targets=["third_party_failure", "schedule_disruption"], rule="exposure_share"),
        Question("recalls_last_5y", "Recall campaigns in the last 5 years", "int", 1,
                 help="Your own history is better evidence than any default.",
                 targets=["product_recall"], rule="recall_history"),
        Question("downtime_cost_per_hour", "Cost of one hour of line downtime", "currency", 45_000, unit="USD",
                 help="Sets what a production delay is actually worth.",
                 targets=["schedule_disruption"], rule="time_cost"),
        Question("commodity_exposure", "Share of COGS exposed to commodity or duty moves", "percent", 0.35,
                 help="More exposed spend, larger cost shock.",
                 targets=["input_cost_shock"], rule="exposure_share"),
        Question("security_maturity", "Security control maturity", "choice", "Developing",
                 choices=["Initial", "Developing", "Defined", "Managed", "Optimizing"],
                 help="Stronger controls lower how often an incident becomes a loss event.",
                 targets=["cyber_loss"], rule="control_maturity"),
    ],
    decisions=[
        Decision(
            id="dual_source_tier1",
            title="Qualify a second source for your most concentrated tier-one",
            question="Should we dual-source the supplier we cannot replace?",
            rationale=(
                "A single-sourced part stops the line. An alternate does not prevent "
                "the supplier failing, it prevents that failure reaching your build."
            ),
            interventions=[
                Intervention("third_party_failure", frequency=0.95, magnitude=0.50),
                Intervention("schedule_disruption", magnitude=0.80),
            ],
            cost_upfront=450_000, cost_annual=220_000, effort="high",
        ),
        Decision(
            id="prerelease_validation",
            title="Extend pre-release validation on your highest-volume line",
            question="Should we add validation before launch rather than after?",
            rationale=(
                "Recalls are rare and enormous. Catching a defect before volume ships "
                "moves both how often a campaign happens and how many units it covers."
            ),
            interventions=[Intervention("product_recall", frequency=0.60, magnitude=0.75)],
            cost_upfront=0, cost_annual=380_000, effort="moderate",
        ),
        Decision(
            id="commodity_hedge",
            title="Hedge or contract your exposed commodity spend",
            question="Should we fix input prices on committed volume?",
            rationale=(
                "You have to buy the material either way. Fixing the price narrows the "
                "range of what it costs you, at the price of the upside."
            ),
            interventions=[Intervention("input_cost_shock", magnitude=0.55)],
            cost_upfront=0, cost_annual=310_000, effort="moderate",
        ),
        Decision(
            id="ot_segmentation",
            title="Segment plant systems from corporate IT",
            question="Should we isolate the network that runs the line?",
            rationale=(
                "Segmentation is what stops an office incident becoming a stopped line. "
                "It cuts frequency of loss events and limits how far one spreads."
            ),
            interventions=[
                Intervention("cyber_loss", frequency=0.60, magnitude=0.80),
                Intervention("schedule_disruption", frequency=0.95),
            ],
            cost_upfront=260_000, cost_annual=120_000, effort="high",
        ),
    ],
    vocabulary={"third_party": "supplier", "schedule": "production", "site": "plant"},
)

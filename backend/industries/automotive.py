"""Automotive & Manufacturing pack. Reference revenue $250M.

A deep pack. The operator enters the parts that stop the line, the programmes
in production, the plants that build them and the commodities they buy, and the
engine parameters are DERIVED from those rather than asked for as percentages.

What that buys: "share of parts that are single-sourced" is a number a
manufacturer has to go and compute. "Which parts are single-sourced, from whom,
on what lead time, at what defect rate" is a table they already maintain. The
product then knows which of those actually stop a build, which is the thing a
plant manager argues about and a generic risk tool cannot see.

Parameters remain starting estimates from expert judgment, not measured loss
data. What changes here is where the INPUTS come from, not the epistemic status
of the calibration.
"""
from engines.decisions import Decision, Intervention
from engines.modulation import Modulation

from .base import EngineBinding, IndustryPack, Question
from .derive import Derivation, centered, derive_all_automotive, response
from .reference import COMMODITY_DISCLAIMER, COMMODITY_VOLATILITY, LAUNCH_STAGE_RISK

# The operation the published calibration describes. A manufacturer whose own
# book matches these gets the pack default back unchanged.
REF_PART_HHI = 0.25            # about four effective suppliers
REF_LINE_STOPPER_SHARE = 0.60
REF_LEAD_DAYS = 60.0
REF_PPM = 82.0
REF_RECALL_EXPOSURE = 55_000_000.0
REF_LAUNCH_RISK = 1.14
REF_TOP_PLANT_SHARE = 0.54
REF_DOWNTIME_COST = 48_000.0
REF_ONE_SIGMA_SWING = 17_800_000.0

DEFAULT_PARTS = [
    {"part": "Transmission housing", "supplier": "Kessler Guss", "annual_spend": 14_500_000,
     "single_source": True, "lead_time_days": 68, "ppm_defect": 85},
    {"part": "Wiring harness", "supplier": "Nuevo Leon Cables", "annual_spend": 9_200_000,
     "single_source": True, "lead_time_days": 47, "ppm_defect": 140},
    {"part": "ECU module", "supplier": "Hanwoo Electronics", "annual_spend": 7_800_000,
     "single_source": False, "lead_time_days": 92, "ppm_defect": 45},
    {"part": "Seat frame", "supplier": "Midwest Stamping", "annual_spend": 4_100_000,
     "single_source": False, "lead_time_days": 21, "ppm_defect": 60},
    {"part": "Brake caliper", "supplier": "Torino Frenos", "annual_spend": 3_400_000,
     "single_source": False, "lead_time_days": 34, "ppm_defect": 30},
]

DEFAULT_PROGRAMS = [
    {"name": "Compact SUV platform", "annual_units": 82_000, "content_value": 310,
     "launch_stage": "Mature"},
    {"name": "Electric crossover", "annual_units": 24_000, "content_value": 690,
     "launch_stage": "Ramp"},
    {"name": "Commercial van", "annual_units": 31_000, "content_value": 420,
     "launch_stage": "Mature"},
]

DEFAULT_PLANTS = [
    {"name": "Toledo assembly", "output_share": 0.54, "downtime_cost_per_hour": 62_000},
    {"name": "Saltillo assembly", "output_share": 0.31, "downtime_cost_per_hour": 38_000},
    {"name": "Greenville components", "output_share": 0.15, "downtime_cost_per_hour": 21_000},
]

DEFAULT_COMMODITIES = [
    {"material": "steel", "annual_spend": 38_000_000, "hedged_share": 0.35},
    {"material": "aluminium", "annual_spend": 16_000_000, "hedged_share": 0.20},
    {"material": "electronics", "annual_spend": 22_000_000, "hedged_share": 0.05},
    {"material": "resin", "annual_spend": 9_000_000, "hedged_share": 0.0},
]


def derive_automotive(answers: dict, marginals: list) -> tuple[dict, list[dict]]:
    """Turn the bill of materials, programme book and plant list into parameters."""
    facts = derive_all_automotive(answers)
    if not facts:
        return {}, []

    d = Derivation()

    # Part concentration against the bill of materials the calibration assumes.
    if facts.get("part_hhi"):
        d.add(
            "third_party_failure",
            Modulation(
                frequency=response(facts["part_hhi"], REF_PART_HHI, 0.25),
                magnitude=response(facts["part_hhi"], REF_PART_HHI, 0.55),
            ),
            "Part spend is concentrated",
            f"{facts['top_part']} from {facts['top_part_supplier']} is "
            f"{facts['top_part_share']:.0%} of part spend; effective supplier count "
            f"{facts['effective_suppliers']} against a reference of {1 / REF_PART_HHI:.1f}",
        )

    # Line stoppers are the real exposure: single-sourced AND long-lead.
    if facts.get("line_stopper_share"):
        s = facts["line_stopper_share"]
        d.add(
            "third_party_failure",
            Modulation(magnitude=centered(s, REF_LINE_STOPPER_SHARE, 0.9)),
            "Some parts have no alternate and a long lead time",
            f"{facts['line_stopper_count']} line-stopping parts, {s:.0%} of spend against a "
            f"{REF_LINE_STOPPER_SHARE:.0%} reference"
            + (f": {', '.join(str(p) for p in facts['line_stopper_parts'])}"
               if facts.get("line_stopper_parts") else ""),
        )
        d.add(
            "schedule_disruption",
            Modulation(frequency=centered(s, REF_LINE_STOPPER_SHARE, 0.7)),
            "A single-sourced long-lead part stops the build",
            f"{facts['line_stopper_count']} parts you cannot resource inside a quarter",
        )

    # Lead time decides how long a stoppage lasts once it starts.
    if facts.get("weighted_lead_days"):
        d.add(
            "schedule_disruption",
            Modulation(magnitude=response(facts["weighted_lead_days"], REF_LEAD_DAYS, 0.70)),
            f"Lead times against a {REF_LEAD_DAYS:.0f}-day reference",
            f"spend-weighted lead time {facts['weighted_lead_days']:.0f} days",
        )

    # Incoming defect rate drives both delay and the recall path.
    if facts.get("weighted_ppm"):
        d.add(
            "product_recall",
            Modulation(frequency=response(facts["weighted_ppm"], REF_PPM, 0.40)),
            f"Incoming defect rate against a {REF_PPM:.0f} PPM reference",
            f"spend-weighted {facts['weighted_ppm']:.0f} PPM across "
            f"{facts['part_count']} parts",
        )

    # Recall exposure is units in the field times content value, and where in
    # its life each programme sits.
    if facts.get("recall_exposure"):
        d.add(
            "product_recall",
            Modulation(magnitude=response(facts["recall_exposure"], REF_RECALL_EXPOSURE, 0.75)),
            "Campaign exposure across programmes in production",
            f"{facts['total_annual_units']:,.0f} units a year, about "
            f"${facts['recall_exposure']:,.0f} of content at risk against a "
            f"${REF_RECALL_EXPOSURE:,.0f} reference; largest is {facts['top_program']}",
        )
    if facts.get("weighted_launch_risk"):
        d.add(
            "product_recall",
            Modulation(frequency=response(facts["weighted_launch_risk"], REF_LAUNCH_RISK, 1.0)),
            "Programmes in ramp carry more defect risk than mature ones",
            f"unit-weighted launch risk {facts['weighted_launch_risk']:.2f}x against a "
            f"{REF_LAUNCH_RISK:.2f}x reference"
            + (f"; in ramp: {', '.join(str(p) for p in facts['programs_in_ramp'])}"
               if facts.get("programs_in_ramp") else ""),
        )

    # Output concentration and what an hour of it is worth.
    if facts.get("top_plant_share"):
        d.add(
            "schedule_disruption",
            Modulation(magnitude=response(facts["top_plant_share"], REF_TOP_PLANT_SHARE, 0.70)),
            "Output is concentrated in one plant",
            f"{facts['top_plant']} builds {facts['top_plant_share']:.0%} of output against a "
            f"{REF_TOP_PLANT_SHARE:.0%} reference",
        )
    if facts.get("weighted_downtime_cost"):
        d.add(
            "schedule_disruption",
            Modulation(magnitude=response(facts["weighted_downtime_cost"], REF_DOWNTIME_COST, 0.80)),
            "What an hour of downtime is actually worth to you",
            f"output-weighted ${facts['weighted_downtime_cost']:,.0f} per hour against a "
            f"${REF_DOWNTIME_COST:,.0f} reference",
        )

    # Cost shock is unhedged spend times how violently those inputs move.
    if facts.get("one_sigma_swing"):
        d.add(
            "input_cost_shock",
            Modulation(magnitude=response(facts["one_sigma_swing"], REF_ONE_SIGMA_SWING, 0.80)),
            "Unhedged commodity spend and how far it can move",
            f"${facts['unhedged_spend']:,.0f} unhedged at a blended "
            f"{facts['blended_volatility']:.0%} volatility, about "
            f"${facts['one_sigma_swing']:,.0f} at one standard deviation against a "
            f"${REF_ONE_SIGMA_SWING:,.0f} reference",
        )

    return d.result(facts)


PACK = IndustryPack(
    id="automotive_manufacturing",
    name="Automotive & Manufacturing",
    tagline="Supplier failure, recall and warranty, production delay, material cost shock.",
    reference_revenue=250_000_000,
    derive=derive_automotive,
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
                 group="Business",
                 help="Scales every loss magnitude. Frequencies stay flat with size.",
                 targets=["*"], rule="revenue_scale"),

        Question("parts", "Parts that would stop a line", "entity_list", DEFAULT_PARTS,
                 group="Bill of materials",
                 help="Concentration, single-source exposure, lead time and defect rate are "
                      "computed from this. A part that is both single-sourced and long-lead is "
                      "flagged as a line stopper.",
                 fields=[
                     {"name": "part", "label": "Part", "type": "text"},
                     {"name": "supplier", "label": "Supplier", "type": "text"},
                     {"name": "annual_spend", "label": "Annual spend", "type": "currency"},
                     {"name": "lead_time_days", "label": "Lead time", "type": "int", "unit": "days"},
                     {"name": "ppm_defect", "label": "Defect rate", "type": "int", "unit": "PPM"},
                     {"name": "single_source", "label": "Single source", "type": "bool"},
                 ],
                 targets=["third_party_failure", "schedule_disruption", "product_recall"],
                 rule="derived"),

        Question("programs", "Programmes in production", "entity_list", DEFAULT_PROGRAMS,
                 group="Programmes",
                 help="Recall exposure is units times content value. Programmes in ramp carry "
                      "more defect risk than mature ones, so we weight by launch stage.",
                 fields=[
                     {"name": "name", "label": "Programme", "type": "text"},
                     {"name": "annual_units", "label": "Annual units", "type": "int"},
                     {"name": "content_value", "label": "Content at risk per unit", "type": "currency"},
                     {"name": "launch_stage", "label": "Launch stage", "type": "choice",
                      "choices": list(LAUNCH_STAGE_RISK.keys())},
                 ],
                 targets=["product_recall"], rule="derived"),

        Question("plants", "Plants", "entity_list", DEFAULT_PLANTS,
                 group="Network",
                 help="Output concentration and what an hour of downtime costs decide what a "
                      "production stoppage is worth.",
                 fields=[
                     {"name": "name", "label": "Plant", "type": "text"},
                     {"name": "output_share", "label": "Share of output", "type": "percent"},
                     {"name": "downtime_cost_per_hour", "label": "Downtime cost per hour",
                      "type": "currency"},
                 ],
                 targets=["schedule_disruption"], rule="derived"),

        Question("commodities", "Commodity spend", "entity_list", DEFAULT_COMMODITIES,
                 group="Purchasing",
                 help="We apply an indicative price volatility to each input class, so you tell "
                      "us what you buy and how much is fixed rather than how volatile it is.",
                 fields=[
                     {"name": "material", "label": "Input", "type": "choice",
                      "choices": sorted(COMMODITY_VOLATILITY.keys())},
                     {"name": "annual_spend", "label": "Annual spend", "type": "currency"},
                     {"name": "hedged_share", "label": "Already fixed or hedged", "type": "percent"},
                 ],
                 targets=["input_cost_shock"], rule="derived"),

        Question("security_maturity", "Security control maturity", "choice", "Developing",
                 group="Controls",
                 choices=["Initial", "Developing", "Defined", "Managed", "Optimizing"],
                 help="Stronger controls lower how often an incident becomes a loss event.",
                 targets=["cyber_loss"], rule="control_maturity"),

        Question("ot_segmentation", "Are plant systems separated from corporate IT?",
                 "choice", "Partially",
                 group="Controls",
                 choices=["Not separated", "Partially", "Mostly", "Fully segmented"],
                 help="Segmentation is what stops an office incident becoming a stopped line.",
                 targets=["cyber_loss"], rule="process_maturity"),
    ],
    decisions=[
        Decision(
            id="dual_source_tier1",
            title="Qualify a second source for {top_part}",
            question="Should we dual-source {top_part} away from {top_part_supplier}?",
            rationale=(
                "{top_part} is {top_part_share_pct} of part spend from {top_part_supplier} "
                "on a {top_part_lead_days_int}-day lead time. An alternate does not stop "
                "them failing, it stops their failure reaching your build."
            ),
            interventions=[
                Intervention("third_party_failure", frequency=0.95, magnitude=0.50),
                Intervention("schedule_disruption", magnitude=0.80),
            ],
            cost_upfront=450_000, cost_annual=220_000, effort="high",
        ),
        Decision(
            id="prerelease_validation",
            title="Extend pre-release validation on {top_program}",
            question="Should we add validation before launch rather than after?",
            rationale=(
                "You have about {recall_exposure_money} of content in the field across "
                "{program_count_int} programmes. Catching a defect before volume ships moves "
                "both how often a campaign happens and how many units it covers."
            ),
            interventions=[Intervention("product_recall", frequency=0.60, magnitude=0.75)],
            cost_upfront=0, cost_annual=380_000, effort="moderate",
        ),
        Decision(
            id="commodity_hedge",
            title="Fix price on your unhedged commodity spend",
            question="Should we hedge or contract the material we buy anyway?",
            rationale=(
                "{unhedged_spend_money} of purchasing is still floating at a blended "
                "{blended_volatility_pct} volatility, about {one_sigma_swing_money} of swing "
                "at one standard deviation. Fixing the price narrows that range at the cost "
                "of the upside."
            ),
            interventions=[Intervention("input_cost_shock", magnitude=0.55)],
            cost_upfront=0, cost_annual=310_000, effort="moderate",
        ),
        Decision(
            id="ot_segmentation",
            title="Segment {top_plant} systems from corporate IT",
            question="Should we isolate the network that runs the line?",
            rationale=(
                "{top_plant} builds {top_plant_share_pct} of output at "
                "{top_plant_downtime_cost_money} an hour of downtime. Segmentation is what "
                "stops an office incident becoming a stopped line."
            ),
            interventions=[
                Intervention("cyber_loss", frequency=0.60, magnitude=0.80),
                Intervention("schedule_disruption", frequency=0.95),
            ],
            cost_upfront=260_000, cost_annual=120_000, effort="high",
        ),
        Decision(
            id="supplier_quality_programme",
            title="Put a resident quality engineer at your worst-PPM suppliers",
            question="Should we fund on-site supplier quality rather than inspect on receipt?",
            rationale=(
                "Incoming quality runs at {weighted_ppm_int} PPM spend-weighted. Defects "
                "caught at the supplier are a scrap cost; the same defect caught in the field "
                "is a campaign."
            ),
            interventions=[
                Intervention("product_recall", frequency=0.75, magnitude=0.85),
                Intervention("schedule_disruption", frequency=0.90),
            ],
            cost_upfront=120_000, cost_annual=265_000, effort="moderate",
        ),
    ],
    vocabulary={
        "third_party": "supplier",
        "schedule": "production",
        "site": "plant",
        "commodity_disclaimer": COMMODITY_DISCLAIMER,
    },
)

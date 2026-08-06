"""Industrial Distribution pack. Reference revenue $120M.

This is the deep pack. Where the other four ask for aggregate percentages, this
one takes the operator's actual vendor book, product lines and sites, then
DERIVES the parameters: concentration from spend shares, duty exposure from HS
chapter and origin, cover from the lines that actually run thin.

The consequence is that the questions are ones only a distributor can answer,
the decisions name their actual vendor and site, and the duty figure comes from
a reference table rather than from asking them what their tariff rate is.

Parameters remain starting estimates from expert judgment, not measured loss
data. What changes here is where the INPUTS come from, not the epistemic status
of the calibration.
"""
from engines.decisions import Decision, Intervention
from engines.modulation import Modulation

from .base import EngineBinding, IndustryPack, Question
from .derive import Derivation, centered, derive_all, response
from .reference import DISCLAIMER, HS_CHAPTERS

# The book the published calibration describes. A distributor whose own numbers
# match these gets the pack default back unchanged; everything here measures
# distance from this operator, not distance from zero.
REF_VENDOR_HHI = 0.36          # about 2.8 effective vendors
REF_SOLE_SOURCE_SHARE = 0.60   # most of the spend has no qualified alternate
REF_LEAD_DAYS = 42.0
REF_DUTY_RATE = 0.185          # meaningful China exposure, which the pack assumes
REF_DAYS_OF_COVER = 41.0
REF_TOP_SITE_SHARE = 0.60

DEFAULT_VENDORS = [
    {"name": "Jiangsu Machine Works", "country": "China", "annual_spend": 3_800_000, "sole_source": True, "lead_time_days": 52},
    {"name": "Nord Hydraulik", "country": "Germany", "annual_spend": 1_600_000, "sole_source": False, "lead_time_days": 34},
    {"name": "Monterrey Castings", "country": "Mexico", "annual_spend": 900_000, "sole_source": False, "lead_time_days": 18},
    {"name": "Osaka Bearings", "country": "Japan", "annual_spend": 700_000, "sole_source": True, "lead_time_days": 41},
]

DEFAULT_LINES = [
    {"name": "Hydraulic pumps", "hs_chapter": "8413", "origin": "China", "annual_import_value": 2_600_000, "days_of_cover": 38},
    {"name": "Ball and roller bearings", "hs_chapter": "8482", "origin": "Japan", "annual_import_value": 1_400_000, "days_of_cover": 26},
    {"name": "Control valves", "hs_chapter": "8481", "origin": "China", "annual_import_value": 1_900_000, "days_of_cover": 44},
    {"name": "Electric motors", "hs_chapter": "8501", "origin": "Germany", "annual_import_value": 1_100_000, "days_of_cover": 61},
]

DEFAULT_SITES = [
    {"name": "Columbus DC", "throughput_share": 0.62},
    {"name": "Reno DC", "throughput_share": 0.26},
    {"name": "Charlotte cross-dock", "throughput_share": 0.12},
]


def derive_distribution(answers: dict, marginals: list) -> tuple[dict, list[dict]]:
    """Turn the operator's own book into parameter adjustments.

    Returns (facts, audit trail). Every adjustment reports the entity-level fact
    that produced it, so the user can see exactly why their number moved.
    """
    facts = derive_all(answers)
    if not facts:
        return {}, []

    d = Derivation()
    add = d.add

    # Vendor concentration, against the book a mid-market distributor typically
    # runs: roughly three effective vendors carrying most of the spend.
    if facts.get("hhi"):
        add(
            "third_party_failure",
            Modulation(
                frequency=response(facts["hhi"], REF_VENDOR_HHI, 0.30),
                magnitude=response(facts["hhi"], REF_VENDOR_HHI, 0.60),
            ),
            "Vendor spend is concentrated",
            f"{facts['top_vendor']} is {facts['top_vendor_share']:.0%} of spend; "
            f"effective vendor count {facts['effective_vendors']} against a reference of "
            f"{1 / REF_VENDOR_HHI:.1f}",
        )

    # Sole-sourcing is the thing that turns a vendor failure into a stoppage.
    if facts.get("sole_source_share"):
        s = facts["sole_source_share"]
        add(
            "third_party_failure",
            Modulation(magnitude=centered(s, REF_SOLE_SOURCE_SHARE, 0.8)),
            "Part of the book has no qualified alternate",
            f"{facts['sole_source_count']} sole-source vendors, {s:.0%} of spend "
            f"against a {REF_SOLE_SOURCE_SHARE:.0%} reference",
        )

    # Lead time drives how long a disruption is felt.
    if facts.get("weighted_lead_days"):
        add(
            "schedule_disruption",
            Modulation(magnitude=response(facts["weighted_lead_days"], REF_LEAD_DAYS, 0.70)),
            f"Lead times against a {REF_LEAD_DAYS:.0f}-day reference",
            f"spend-weighted lead time {facts['weighted_lead_days']:.0f} days",
        )

    # Duty exposure comes from the reference table, not from asking them.
    if facts.get("blended_duty_rate"):
        add(
            "input_cost_shock",
            Modulation(magnitude=response(facts["blended_duty_rate"], REF_DUTY_RATE, 0.80)),
            f"Duty exposure against a {REF_DUTY_RATE:.0%} reference",
            f"blended {facts['blended_duty_rate']:.1%} across {facts['line_count']} lines, "
            f"about ${facts['annual_duty_cost']:,.0f} a year",
        )

    # Thin cover is what turns a delay into a lost sale. Inverted: more cover
    # is less exposure.
    if facts.get("weighted_days_of_cover"):
        add(
            "inventory_stockout",
            Modulation(frequency=response(REF_DAYS_OF_COVER, facts["weighted_days_of_cover"], 0.80)),
            f"Cover against a {REF_DAYS_OF_COVER:.0f}-day reference",
            f"weighted cover {facts['weighted_days_of_cover']:.0f} days"
            + (f"; thin on {', '.join(facts['thin_cover_lines'])}" if facts.get("thin_cover_lines") else ""),
        )

    # Throughput concentration across sites.
    if facts.get("top_site_share"):
        add(
            "site_disruption",
            Modulation(magnitude=response(facts["top_site_share"], REF_TOP_SITE_SHARE, 0.70)),
            "Throughput is concentrated in one site",
            f"{facts['top_site']} handles {facts['top_site_share']:.0%} of throughput "
            f"against a {REF_TOP_SITE_SHARE:.0%} reference",
        )

    return d.result(facts)


PACK = IndustryPack(
    id="industrial_distribution",
    name="Industrial Distribution",
    tagline="Tariff shock, vendor failure, logistics delay, stockout, warehouse outage.",
    reference_revenue=120_000_000,
    derive=derive_distribution,
    bindings=[
        EngineBinding(
            "input_cost_shock", "Tariff shock", (0.30, 0.80, 1.50), (450_000, 1_400_000),
            "An adverse move in duties or landed cost on the goods you import.",
        ),
        EngineBinding(
            "third_party_failure", "Vendor failure", (0.15, 0.40, 1.00), (250_000, 900_000),
            "A vendor you depend on cannot supply on the terms you planned for.",
        ),
        EngineBinding(
            "schedule_disruption", "Logistics delay", (0.40, 1.00, 2.20), (150_000, 700_000),
            "Freight, customs or carrier delay pushes delivery past commitment.",
        ),
        EngineBinding(
            "inventory_stockout", "Stockout", (0.30, 0.70, 1.60), (200_000, 800_000),
            "Demand outruns cover and you lose margin or expedite to recover.",
        ),
        EngineBinding(
            "site_disruption", "Warehouse outage", (0.08, 0.20, 0.50), (400_000, 1_800_000),
            "A distribution centre becomes unavailable.",
        ),
        EngineBinding(
            "cyber_loss", "Cyber incident", (0.05, 0.15, 0.45), (180_000, 1_100_000),
            "A security or data incident interrupts operations.",
        ),
    ],
    correlation_pairs={
        ("third_party_failure", "schedule_disruption"): 0.65,
        ("schedule_disruption", "inventory_stockout"): 0.60,
        ("input_cost_shock", "third_party_failure"): 0.45,
        ("input_cost_shock", "inventory_stockout"): 0.40,
    },
    questions=[
        Question("annual_revenue", "Annual revenue", "currency", 120_000_000, unit="USD",
                 group="Business",
                 help="Scales every loss magnitude. Frequencies stay flat with size.",
                 targets=["*"], rule="revenue_scale"),

        Question("vendors", "Your top vendors by spend", "entity_list", DEFAULT_VENDORS,
                 group="Vendor book",
                 help="Concentration, sole-source exposure and lead time are computed from this, "
                      "not asked for separately.",
                 fields=[
                     {"name": "name", "label": "Vendor", "type": "text"},
                     {"name": "country", "label": "Country", "type": "text"},
                     {"name": "annual_spend", "label": "Annual spend", "type": "currency"},
                     {"name": "lead_time_days", "label": "Lead time", "type": "int", "unit": "days"},
                     {"name": "sole_source", "label": "Sole source", "type": "bool"},
                 ],
                 targets=["third_party_failure", "schedule_disruption"], rule="derived"),

        Question("product_lines", "Product lines you import", "entity_list", DEFAULT_LINES,
                 group="Import book",
                 help="We look up the duty rate for each HS chapter and origin, so you do not have "
                      "to tell us your tariff exposure.",
                 fields=[
                     {"name": "name", "label": "Line", "type": "text"},
                     {"name": "hs_chapter", "label": "HS chapter", "type": "choice",
                      "choices": sorted(HS_CHAPTERS.keys())},
                     {"name": "origin", "label": "Origin", "type": "text"},
                     {"name": "annual_import_value", "label": "Annual import value", "type": "currency"},
                     {"name": "days_of_cover", "label": "Days of cover", "type": "int", "unit": "days"},
                 ],
                 targets=["input_cost_shock", "inventory_stockout"], rule="derived"),

        Question("sites", "Distribution centres", "entity_list", DEFAULT_SITES,
                 group="Network",
                 help="Throughput concentration decides how much a single site outage costs.",
                 fields=[
                     {"name": "name", "label": "Site", "type": "text"},
                     {"name": "throughput_share", "label": "Share of throughput", "type": "percent"},
                 ],
                 targets=["site_disruption"], rule="derived"),

        Question("security_maturity", "Security control maturity", "choice", "Developing",
                 group="Controls",
                 choices=["Initial", "Developing", "Defined", "Managed", "Optimizing"],
                 help="Stronger controls lower how often an incident becomes a loss event.",
                 targets=["cyber_loss"], rule="control_maturity"),

        Question("contract_terms", "Do your customer contracts pass through cost increases?",
                 "choice", "Partially",
                 group="Controls",
                 choices=["No pass-through", "Partially", "Mostly", "Fully indexed"],
                 help="Pass-through decides how much of a duty or freight move you actually absorb.",
                 targets=["input_cost_shock"], rule="process_maturity"),
    ],
    decisions=[
        Decision(
            id="dual_source_top_vendor",
            title="Qualify a second source for {top_vendor}",
            question="Should we dual-source {top_vendor}?",
            rationale=(
                "{top_vendor} is {top_vendor_share_pct} of your vendor spend on a "
                "{top_vendor_lead_days_int}-day lead time. A qualified alternate does not stop them "
                "failing, it stops their failure stopping you."
            ),
            interventions=[
                Intervention("third_party_failure", frequency=0.95, magnitude=0.55),
                Intervention("schedule_disruption", magnitude=0.85),
            ],
            cost_upfront=180_000, cost_annual=95_000, effort="high",
        ),
        Decision(
            id="raise_days_of_cover",
            title="Raise cover on your thin lines",
            question="Should we hold more inventory on the lines that run thin?",
            rationale=(
                "Weighted cover is {weighted_days_of_cover_int} days against a 45-day reference. "
                "Cover absorbs delay before it becomes a lost sale."
            ),
            interventions=[
                Intervention("inventory_stockout", frequency=0.60, magnitude=0.85),
                Intervention("schedule_disruption", magnitude=0.90),
            ],
            cost_upfront=0, cost_annual=240_000, effort="low",
        ),
        Decision(
            id="tariff_hedge",
            title="Lock landed cost on your exposed import volume",
            question="Should we fix duty and freight terms rather than float?",
            rationale=(
                "You are carrying about {annual_duty_cost_money} a year in duty at a blended "
                "{blended_duty_rate_pct}. Fixing terms trades upside for a narrower range."
            ),
            interventions=[Intervention("input_cost_shock", magnitude=0.55)],
            cost_upfront=0, cost_annual=185_000, effort="moderate",
        ),
        Decision(
            id="second_dc",
            title="Establish failover for {top_site}",
            question="Should we stand up a backup for {top_site}?",
            rationale=(
                "{top_site} carries {top_site_share_pct} of throughput. Failover does not make an "
                "outage less likely, it makes one survivable."
            ),
            interventions=[Intervention("site_disruption", magnitude=0.45)],
            cost_upfront=420_000, cost_annual=130_000, effort="high",
        ),
        Decision(
            id="security_uplift",
            title="Advance security controls one maturity level",
            question="Should we fund the next step of the security roadmap?",
            rationale=(
                "Stronger controls reduce how often an incident becomes a loss event. A breach "
                "still costs what it costs; there are just fewer of them."
            ),
            interventions=[Intervention("cyber_loss", frequency=0.65)],
            cost_upfront=90_000, cost_annual=145_000, effort="moderate",
        ),
    ],
    vocabulary={
        "counterparty": "customer",
        "site": "warehouse",
        "third_party": "vendor",
        "schedule": "logistics",
        "duty_disclaimer": DISCLAIMER,
    },
)

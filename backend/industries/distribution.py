"""Industrial Distribution pack. Reference revenue $120M.

Parameters are starting estimates from expert judgment, not measured loss data.
They are editable everywhere they appear and the sensitivity output shows which
of them actually move the answer.
"""
from engines.decisions import Decision, Intervention

from .base import EngineBinding, IndustryPack, Question

PACK = IndustryPack(
    id="industrial_distribution",
    name="Industrial Distribution",
    tagline="Tariff shock, vendor failure, logistics delay, stockout, warehouse outage.",
    reference_revenue=120_000_000,
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
    # Section 2.6 text matrix: four named pairs over a 0.20 baseline. Canonical.
    correlation_pairs={
        ("third_party_failure", "schedule_disruption"): 0.65,
        ("schedule_disruption", "inventory_stockout"): 0.60,
        ("input_cost_shock", "third_party_failure"): 0.45,
        ("input_cost_shock", "inventory_stockout"): 0.40,
    },
    questions=[
        Question(
            "annual_revenue", "Annual revenue", "currency", 120_000_000, unit="USD",
            help="Scales every loss magnitude. Frequencies stay flat with size.",
            targets=["*"], rule="revenue_scale",
        ),
        Question(
            "imported_share", "Share of goods imported", "percent", 0.45,
            help="More imported volume raises tariff and logistics exposure.",
            targets=["input_cost_shock", "schedule_disruption"], rule="exposure_share",
        ),
        Question(
            "top_vendor_share", "Share of spend with your largest vendor", "percent", 0.30,
            help="Concentration raises both how often a vendor failure bites and how much it costs.",
            targets=["third_party_failure"], rule="concentration",
        ),
        Question(
            "days_of_cover", "Inventory days of cover", "int", 45, unit="days",
            help="More cover absorbs delay before it becomes a stockout.",
            targets=["inventory_stockout"], rule="days_of_cover",
        ),
        Question(
            "warehouse_count", "Number of distribution centres", "int", 3,
            help="A single site concentrates outage risk; more sites spread it.",
            targets=["site_disruption"], rule="site_count",
        ),
        Question(
            "top_customer_share", "Share of revenue from your largest customer", "percent", 0.18,
            help="Captured for interpretation. Customer concentration is not one of this pack's engines.",
            context_only=True,
        ),
        Question(
            "security_maturity", "Security control maturity", "choice", "Developing",
            choices=["Initial", "Developing", "Defined", "Managed", "Optimizing"],
            help="Stronger controls lower how often an incident becomes a loss event.",
            targets=["cyber_loss"], rule="control_maturity",
        ),
    ],
    decisions=[
        Decision(
            id="dual_source_top_vendor",
            title="Qualify a second source for your largest vendor",
            question="Should we dual-source the line we buy most of?",
            rationale=(
                "Concentration is what turns a vendor problem into your problem. A "
                "qualified alternate does not stop the failure, it stops the failure "
                "from stopping you, so it cuts severity far more than frequency."
            ),
            interventions=[
                Intervention("third_party_failure", frequency=0.95, magnitude=0.55),
                Intervention("schedule_disruption", magnitude=0.85),
            ],
            cost_upfront=180_000, cost_annual=95_000, effort="high",
        ),
        Decision(
            id="raise_days_of_cover",
            title="Raise days of cover on your fastest-moving lines",
            question="Should we hold more inventory on the lines that stock out?",
            rationale=(
                "Cover is a buffer that absorbs delay before it becomes a lost sale. "
                "It mostly prevents the stockout rather than shrinking it, and it "
                "also absorbs part of a logistics delay."
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
                "Fixing terms trades some upside for a much narrower range. It does "
                "not change how often trade policy moves, it changes how much of that "
                "move lands on you."
            ),
            interventions=[Intervention("input_cost_shock", magnitude=0.55)],
            cost_upfront=0, cost_annual=185_000, effort="moderate",
        ),
        Decision(
            id="second_dc",
            title="Establish failover for your primary distribution centre",
            question="Should we stand up a backup site for our busiest DC?",
            rationale=(
                "A single site concentrates outage risk. Failover does not make an "
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
                "Stronger controls reduce how often an incident becomes a loss event. "
                "A breach still costs what it costs; there are just fewer of them."
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
    },
)

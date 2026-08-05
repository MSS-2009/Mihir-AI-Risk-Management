"""Industrial Distribution pack. Reference revenue $120M.

Parameters are starting estimates from expert judgment, not measured loss data.
They are editable everywhere they appear and the sensitivity output shows which
of them actually move the answer.
"""
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
    vocabulary={
        "counterparty": "customer",
        "site": "warehouse",
        "third_party": "vendor",
        "schedule": "logistics",
    },
)

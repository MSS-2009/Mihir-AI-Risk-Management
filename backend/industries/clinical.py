"""Clinical Research & Healthcare pack. Reference revenue $60M.

Parameters are starting estimates from expert judgment, not measured loss data.
This matters more here than anywhere else in the product: implying empirical
grounding we do not have, in a regulated setting, would shade into
misrepresentation. Every default is labelled as an editable starting estimate
and the sensitivity output shows which judgments actually drive the answer.
"""
from engines.decisions import Decision, Intervention

from .base import EngineBinding, IndustryPack, Question

PACK = IndustryPack(
    id="clinical_research",
    name="Clinical Research & Healthcare",
    tagline="Enrollment delay, patient-data incident, protocol deviation, site and sponsor dependency.",
    reference_revenue=60_000_000,
    bindings=[
        EngineBinding(
            "schedule_disruption", "Enrollment delay", (0.30, 0.70, 1.60), (220_000, 1_000_000),
            "Recruitment runs behind plan and pushes milestones out.",
        ),
        EngineBinding(
            "cyber_loss", "Patient-data incident", (0.03, 0.10, 0.30), (450_000, 3_500_000),
            "An incident exposes patient or trial data.",
        ),
        EngineBinding(
            "regulatory_compliance_failure", "Protocol or reporting failure", (0.06, 0.15, 0.45), (300_000, 2_200_000),
            "A protocol deviation or adverse-event reporting failure requires remediation.",
        ),
        EngineBinding(
            "site_disruption", "Trial site outage", (0.20, 0.50, 1.20), (200_000, 900_000),
            "A trial site cannot operate or loses its investigator.",
        ),
        EngineBinding(
            "counterparty_concentration", "Sponsor concentration", (0.06, 0.15, 0.40), (600_000, 2_500_000),
            "A sponsor cancels, pauses or does not renew a programme.",
        ),
    ],
    correlation_pairs={
        ("schedule_disruption", "site_disruption"): 0.55,
        ("cyber_loss", "regulatory_compliance_failure"): 0.60,
        ("regulatory_compliance_failure", "counterparty_concentration"): 0.45,
        ("schedule_disruption", "counterparty_concentration"): 0.40,
    },
    questions=[
        Question("annual_revenue", "Annual revenue", "currency", 60_000_000, unit="USD",
                 help="Scales every loss magnitude. Frequencies stay flat with size.",
                 targets=["*"], rule="revenue_scale"),
        Question("trial_phase", "Predominant trial phase", "choice", "Phase II",
                 choices=["Phase I", "Phase II", "Phase III", "Phase IV"],
                 help="Later phases carry larger enrollment commitments and larger delay costs.",
                 targets=["schedule_disruption"], rule="time_cost"),
        Question("enrollment_vs_plan", "Enrollment rate against plan", "percent", 0.85,
                 help="Running behind plan raises how often a delay becomes a loss event.",
                 targets=["schedule_disruption"], rule="buffer"),
        Question("active_sites", "Number of active trial sites", "int", 12,
                 help="More sites spread outage exposure; few sites concentrate it.",
                 targets=["site_disruption"], rule="site_count"),
        Question("phi_records", "Patient records held", "int", 40_000,
                 help="More records held, larger incident magnitude.",
                 targets=["cyber_loss"], rule="records_held"),
        Question("data_controls", "Patient-data control maturity", "choice", "Defined",
                 choices=["Initial", "Developing", "Defined", "Managed", "Optimizing"],
                 help="Stronger controls lower how often an incident becomes a loss event.",
                 targets=["cyber_loss"], rule="control_maturity"),
        Question("deviations_last_year", "Protocol deviations logged last year", "int", 4,
                 help="Your own history is better evidence than any default.",
                 targets=["regulatory_compliance_failure"], rule="recall_history"),
        Question("top_sponsor_share", "Share of revenue from your largest sponsor", "percent", 0.35,
                 help="Concentration raises both the odds and the cost of losing a sponsor.",
                 targets=["counterparty_concentration"], rule="concentration"),
    ],
    decisions=[
        Decision(
            id="add_sites",
            title="Activate additional trial sites",
            question="Should we open more sites to protect the enrollment curve?",
            rationale=(
                "More sites both spread outage exposure and give recruitment more "
                "places to come from, which is the main defence against slipping."
            ),
            interventions=[
                Intervention("site_disruption", magnitude=0.55),
                Intervention("schedule_disruption", frequency=0.75),
            ],
            cost_upfront=190_000, cost_annual=240_000, effort="high",
        ),
        Decision(
            id="monitoring_uplift",
            title="Move protocol monitoring from periodic to risk-based continuous",
            question="Should we monitor continuously rather than on a schedule?",
            rationale=(
                "Deviations found early are documentation problems. Found late they "
                "are findings. This mostly changes how often one escalates."
            ),
            interventions=[Intervention("regulatory_compliance_failure", frequency=0.60, magnitude=0.80)],
            cost_upfront=0, cost_annual=260_000, effort="moderate",
        ),
        Decision(
            id="phi_controls",
            title="Advance patient-data controls one maturity level",
            question="Should we fund the next step of data protection?",
            rationale=(
                "A patient-data incident is both a loss and a regulatory event. "
                "Controls reduce how often one occurs."
            ),
            interventions=[
                Intervention("cyber_loss", frequency=0.60),
                Intervention("regulatory_compliance_failure", frequency=0.85),
            ],
            cost_upfront=140_000, cost_annual=175_000, effort="moderate",
        ),
        Decision(
            id="sponsor_diversification",
            title="Reduce dependence on your largest sponsor",
            question="Should we invest in business development to spread sponsors?",
            rationale=(
                "One sponsor pausing a programme should not decide your year. "
                "Spreading the book lowers what any single pause costs."
            ),
            interventions=[Intervention("counterparty_concentration", magnitude=0.60)],
            cost_upfront=0, cost_annual=230_000, effort="high",
        ),
    ],
    vocabulary={"counterparty": "sponsor", "site": "trial site", "schedule": "enrollment"},
)

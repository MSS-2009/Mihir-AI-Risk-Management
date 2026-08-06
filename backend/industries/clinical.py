"""Clinical Research & Healthcare pack. Reference revenue $60M.

A deep pack. The operator enters their protocol book and the systems holding
patient data, and the parameters are DERIVED: enrollment risk from the gap
against target weighted by how hard each therapeutic area recruits, sponsor
concentration from who is paying for which trial, breach exposure from the
systems actually flagged as holding PHI.

The sponsor question disappears entirely as a result. A CRO should not be asked
"what share of revenue comes from your largest sponsor" when they have just
listed every trial and who sponsors it. Deriving it is both less work for them
and harder to get wrong.

Parameters are starting estimates from expert judgment, not measured loss data.
This matters more here than anywhere else in the product: implying empirical
grounding we do not have, in a regulated setting, would shade into
misrepresentation. Every default is labelled as an editable starting estimate,
the therapeutic-area reference table carries its own disclaimer, and the
sensitivity output shows which judgments actually drive the answer.
"""
from engines.decisions import Decision, Intervention
from engines.modulation import Modulation

from .base import EngineBinding, IndustryPack, Question
from .derive import Derivation, centered, derive_all_clinical, response
from .reference import CLINICAL_DISCLAIMER, PHASE_DELAY_COST, THERAPEUTIC_AREAS

# The book the published calibration describes. A CRO whose own protocols match
# these gets the pack default back unchanged.
REF_ENROLLMENT_GAP = 0.35
REF_DIFFICULTY = 1.42
REF_PHASE_COST = 1.52
REF_SITES = 96.0
REF_SPONSOR_HHI = 0.44
REF_PHI_RECORDS = 85_000.0
REF_VENDOR_HOSTED_SHARE = 0.86

DEFAULT_TRIALS = [
    {"name": "AVN-201 first-line NSCLC", "phase": "Phase III", "therapeutic_area": "Oncology",
     "sponsor": "Meridian Bio", "annual_value": 18_000_000,
     "target_enrollment": 420, "enrolled_to_date": 240, "sites_activated": 28},
    {"name": "AVN-330 rare metabolic", "phase": "Phase II", "therapeutic_area": "Rare disease",
     "sponsor": "Meridian Bio", "annual_value": 12_000_000,
     "target_enrollment": 90, "enrolled_to_date": 38, "sites_activated": 22},
    {"name": "AVN-087 heart failure", "phase": "Phase III", "therapeutic_area": "Cardiology",
     "sponsor": "Corvin Pharma", "annual_value": 11_000_000,
     "target_enrollment": 600, "enrolled_to_date": 510, "sites_activated": 34},
    {"name": "AVN-114 atopic dermatitis", "phase": "Phase II", "therapeutic_area": "Dermatology",
     "sponsor": "Halden Therapeutics", "annual_value": 9_000_000,
     "target_enrollment": 180, "enrolled_to_date": 155, "sites_activated": 12},
]

DEFAULT_DATA_SYSTEMS = [
    {"name": "EDC platform", "records": 42_000, "holds_phi": True, "vendor_hosted": True},
    {"name": "Central lab portal", "records": 31_000, "holds_phi": True, "vendor_hosted": True},
    {"name": "Site coordination CRM", "records": 12_000, "holds_phi": True, "vendor_hosted": False},
    {"name": "Electronic trial master file", "records": 8_000, "holds_phi": False, "vendor_hosted": True},
]


def derive_clinical(answers: dict, marginals: list) -> tuple[dict, list[dict]]:
    """Turn the protocol book and data estate into parameters."""
    facts = derive_all_clinical(answers)
    if not facts:
        return {}, []

    d = Derivation()

    # Enrollment risk: the gap against target, scaled by how hard the areas you
    # are actually recruiting in are to recruit.
    if facts.get("weighted_enrollment_gap") is not None:
        gap = facts["weighted_enrollment_gap"]
        d.add(
            "schedule_disruption",
            Modulation(frequency=response(max(gap, 0.01), REF_ENROLLMENT_GAP, 0.55)),
            f"Enrollment shortfall against a {REF_ENROLLMENT_GAP:.0%} reference gap",
            f"value-weighted gap {gap:.0%} across {facts['trial_count']} trials"
            + (f"; behind on {', '.join(str(t) for t in facts['trials_behind'])}"
               if facts.get("trials_behind") else ""),
        )
    if facts.get("weighted_difficulty"):
        d.add(
            "schedule_disruption",
            Modulation(frequency=response(facts["weighted_difficulty"], REF_DIFFICULTY, 0.60)),
            "How hard your therapeutic areas are to recruit",
            f"value-weighted difficulty {facts['weighted_difficulty']:.2f}x against a "
            f"{REF_DIFFICULTY:.2f}x reference",
        )
    if facts.get("weighted_phase_cost"):
        d.add(
            "schedule_disruption",
            Modulation(magnitude=response(facts["weighted_phase_cost"], REF_PHASE_COST, 0.80)),
            "What a month of delay costs at the phases you are running",
            f"value-weighted phase cost {facts['weighted_phase_cost']:.2f}x against a "
            f"{REF_PHASE_COST:.2f}x reference",
        )

    # Site count spreads outage exposure but gives more places to fail.
    if facts.get("sites_activated"):
        n = float(facts["sites_activated"])
        d.add(
            "site_disruption",
            Modulation(
                frequency=response(n, REF_SITES, 0.30),
                magnitude=response(REF_SITES, n, 0.70),
            ),
            f"Site network against a {REF_SITES:.0f}-site reference",
            f"{facts['sites_activated']} sites activated across {facts['trial_count']} trials",
        )

    # Sponsor concentration falls out of the trial book rather than being asked.
    if facts.get("sponsor_hhi"):
        d.add(
            "counterparty_concentration",
            Modulation(
                frequency=response(facts["sponsor_hhi"], REF_SPONSOR_HHI, 0.30),
                magnitude=response(facts["sponsor_hhi"], REF_SPONSOR_HHI, 0.65),
            ),
            "Trial value is concentrated in few sponsors",
            f"{facts['top_sponsor']} funds {facts['top_sponsor_share']:.0%} of trial value "
            f"across {facts['sponsor_count']} sponsors",
        )

    # Breach magnitude from the systems that actually hold PHI.
    if facts.get("phi_records"):
        d.add(
            "cyber_loss",
            Modulation(magnitude=response(facts["phi_records"], REF_PHI_RECORDS, 0.60)),
            f"Patient records held against a {REF_PHI_RECORDS:,.0f} reference",
            f"{facts['phi_records']:,.0f} records across {facts['phi_system_count']} systems "
            f"flagged as holding PHI",
        )
    if facts.get("vendor_hosted_phi_share"):
        s = facts["vendor_hosted_phi_share"]
        d.add(
            "cyber_loss",
            Modulation(frequency=centered(s, REF_VENDOR_HOSTED_SHARE, 0.35)),
            "PHI sitting outside your own estate",
            f"{s:.0%} of patient records are vendor-hosted against a "
            f"{REF_VENDOR_HOSTED_SHARE:.0%} reference",
        )
        d.add(
            "regulatory_compliance_failure",
            Modulation(frequency=centered(s, REF_VENDOR_HOSTED_SHARE, 0.25)),
            "Vendor-held data is still your reporting obligation",
            f"{s:.0%} of PHI is vendor-hosted",
        )

    return d.result(facts)


PACK = IndustryPack(
    id="clinical_research",
    name="Clinical Research & Healthcare",
    tagline="Enrollment delay, patient-data incident, protocol deviation, site and sponsor dependency.",
    reference_revenue=60_000_000,
    derive=derive_clinical,
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
                 group="Business",
                 help="Scales every loss magnitude. Frequencies stay flat with size.",
                 targets=["*"], rule="revenue_scale"),

        Question("trials", "Trials you are running", "entity_list", DEFAULT_TRIALS,
                 group="Protocol book",
                 help="Enrollment risk, phase delay cost and sponsor concentration are all "
                      "computed from this. We apply a screen-failure and difficulty profile "
                      "per therapeutic area, so oncology and dermatology are not treated alike.",
                 fields=[
                     {"name": "name", "label": "Trial", "type": "text"},
                     {"name": "phase", "label": "Phase", "type": "choice",
                      "choices": list(PHASE_DELAY_COST.keys())},
                     {"name": "therapeutic_area", "label": "Therapeutic area", "type": "choice",
                      "choices": list(THERAPEUTIC_AREAS.keys())},
                     {"name": "sponsor", "label": "Sponsor", "type": "text"},
                     {"name": "annual_value", "label": "Annual value", "type": "currency"},
                     {"name": "target_enrollment", "label": "Target enrollment", "type": "int"},
                     {"name": "enrolled_to_date", "label": "Enrolled to date", "type": "int"},
                     {"name": "sites_activated", "label": "Sites activated", "type": "int"},
                 ],
                 targets=["schedule_disruption", "site_disruption", "counterparty_concentration"],
                 rule="derived"),

        Question("data_systems", "Systems holding trial data", "entity_list", DEFAULT_DATA_SYSTEMS,
                 group="Data estate",
                 help="Breach magnitude counts only systems flagged as holding PHI, and we "
                      "separate what sits with a vendor from what sits with you.",
                 fields=[
                     {"name": "name", "label": "System", "type": "text"},
                     {"name": "records", "label": "Records", "type": "int"},
                     {"name": "holds_phi", "label": "Holds PHI", "type": "bool"},
                     {"name": "vendor_hosted", "label": "Vendor hosted", "type": "bool"},
                 ],
                 targets=["cyber_loss", "regulatory_compliance_failure"], rule="derived"),

        Question("data_controls", "Patient-data control maturity", "choice", "Defined",
                 group="Controls",
                 choices=["Initial", "Developing", "Defined", "Managed", "Optimizing"],
                 help="Stronger controls lower how often an incident becomes a loss event.",
                 targets=["cyber_loss"], rule="control_maturity"),

        Question("monitoring", "Protocol monitoring approach", "choice", "Periodic",
                 group="Controls",
                 choices=["Ad hoc", "Periodic", "Systematic", "Independently audited"],
                 help="A systematic process catches deviations while they are still fixable.",
                 targets=["regulatory_compliance_failure"], rule="process_maturity"),

        Question("deviations_last_year", "Protocol deviations logged last year", "int", 4,
                 group="Controls",
                 help="Your own history is better evidence than any default.",
                 targets=["regulatory_compliance_failure"], rule="recall_history"),
    ],
    decisions=[
        Decision(
            id="add_sites",
            title="Activate additional sites on {worst_gap_trial}",
            question="Should we open more sites to protect the enrollment curve?",
            rationale=(
                "{worst_gap_trial} is {worst_gap_pct} short of target, in an area that "
                "recruits at {weighted_difficulty} times the reference difficulty. More sites "
                "both spread outage exposure and give recruitment more places to come from."
            ),
            interventions=[
                Intervention("site_disruption", magnitude=0.55),
                Intervention("schedule_disruption", frequency=0.75),
            ],
            cost_upfront=190_000, cost_annual=240_000, effort="high",
        ),
        Decision(
            id="monitoring_uplift",
            title="Move protocol monitoring to risk-based continuous",
            question="Should we monitor continuously rather than on a schedule?",
            rationale=(
                "Deviations found early are documentation problems. Found late they are "
                "findings. This mostly changes how often one escalates."
            ),
            interventions=[Intervention("regulatory_compliance_failure", frequency=0.60, magnitude=0.80)],
            cost_upfront=0, cost_annual=260_000, effort="moderate",
        ),
        Decision(
            id="phi_controls",
            title="Advance patient-data controls one maturity level",
            question="Should we fund the next step of data protection?",
            rationale=(
                "You hold {phi_records_int} patient records across "
                "{phi_system_count_int} systems, {vendor_hosted_phi_share_pct} of them "
                "vendor-hosted. A patient-data incident is both a loss and a regulatory event."
            ),
            interventions=[
                Intervention("cyber_loss", frequency=0.60),
                Intervention("regulatory_compliance_failure", frequency=0.85),
            ],
            cost_upfront=140_000, cost_annual=175_000, effort="moderate",
        ),
        Decision(
            id="sponsor_diversification",
            title="Reduce dependence on {top_sponsor}",
            question="Should we invest in business development to spread sponsors?",
            rationale=(
                "{top_sponsor} funds {top_sponsor_share_pct} of trial value. One sponsor "
                "pausing a programme should not decide your year."
            ),
            interventions=[Intervention("counterparty_concentration", magnitude=0.60)],
            cost_upfront=0, cost_annual=230_000, effort="high",
        ),
        Decision(
            id="vendor_data_audit",
            title="Audit and tighten vendor-held patient data",
            question="Should we audit the vendors holding our PHI?",
            rationale=(
                "{vendor_hosted_phi_share_pct} of your patient records sit outside your own "
                "estate. The obligation to report a breach of them does not."
            ),
            interventions=[
                Intervention("cyber_loss", frequency=0.80, magnitude=0.90),
                Intervention("regulatory_compliance_failure", frequency=0.85),
            ],
            cost_upfront=75_000, cost_annual=90_000, effort="low",
        ),
    ],
    vocabulary={
        "counterparty": "sponsor",
        "site": "trial site",
        "schedule": "enrollment",
        "enrollment_disclaimer": CLINICAL_DISCLAIMER,
    },
)

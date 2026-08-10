"""What a document means, per industry.

The extractor used to know one world: purchase orders, HS codes, lead times.
That is the right vocabulary for a distributor and useless to everyone else. A
CRO uploading a clinical trial agreement got a "commercial invoice" back with
every field null, which is worse than refusing, because it looks like the
product tried and had nothing to say.

So each industry declares three things:

  doc_types   what paperwork this operator actually has, and the keywords that
              identify it when no extraction key is present
  schema      the fields worth pulling out of that paperwork
  tables      how those fields become rows in the pack's own entity tables

Adding an industry means adding a profile here. No extractor code changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocType:
    id: str
    name: str
    description: str
    keywords: list[str]
    unlocks: list[str] = field(default_factory=list)
    required: bool = False


# How a column is combined when several documents describe the same entity.
#
#   sum    transactional amounts: three purchase orders are three orders. Values
#          that repeat identically are treated as one, because a PO, its invoice
#          and the customs entry for one shipment all carry the same figure.
#   max    stocks and rates: AUM, record counts, an annual contract value and a
#          lead time are not additive. Two custodial statements for one client
#          are one client's money counted twice if you add them.
#   first  text and categorical.
#   any    booleans: true if any document evidences it.
SUM, MAX, FIRST, ANY = "sum", "max", "first", "any"


@dataclass(frozen=True)
class TableMap:
    """One of the pack's entity tables, and how documents fill it."""

    question: str                  # entity_list question id in the industry pack
    key: str                       # extraction field that identifies one row
    columns: dict[str, tuple]      # entity column -> (extraction field, how to combine)
    label_from: tuple = ()         # fields to build a name from when key is not a name
    needs: tuple = ()              # at least one of these must be evidenced to emit a row
    alt_keys: tuple = ()           # used when no document names the primary key


@dataclass(frozen=True)
class DocProfile:
    industry: str
    role: str                      # how the extractor introduces itself
    doc_types: list[DocType]
    schema: dict[str, str]
    tables: list[TableMap]
    # What the tables inside this industry's reports usually enumerate. Without
    # this the extractor reads a six-row sponsor revenue schedule as one record
    # and the operator's own concentration never reaches the model.
    row_hints: tuple = ()

    @property
    def keywords(self) -> dict[str, list[str]]:
        return {d.id: d.keywords for d in self.doc_types}

    @property
    def default_doc_type(self) -> str:
        return self.doc_types[0].id


# ---------------------------------------------------------------------------
# Industrial distribution: the original trade-document world.
# ---------------------------------------------------------------------------

DISTRIBUTION = DocProfile(
    industry="industrial_distribution",
    role="trade-document analyst",
    doc_types=[
        DocType("purchase_order", "Purchase Orders",
                "Supplier, quantities and committed spend per line.",
                ["purchase order", "p.o.", "po number", "po #", "order confirmation"],
                ["third_party_failure"], True),
        DocType("commercial_invoice", "Commercial Invoices",
                "Import value, unit price and country of origin.",
                ["commercial invoice", "invoice no", "invoice number", "bill to", "sold to"],
                ["input_cost_shock"], True),
        DocType("customs_paperwork", "Customs paperwork",
                "HS classification and duty actually paid.",
                ["customs", "hs code", "harmonized", "entry summary", "7501", "duty rate", "tariff"],
                ["input_cost_shock"], True),
        DocType("bill_of_lading", "Bills of Lading",
                "Carrier, route and dates, for lead-time history.",
                ["bill of lading", "b/l no", "shipper", "consignee", "vessel", "port of loading"],
                ["schedule_disruption"], True),
        DocType("packing_list", "Packing Lists",
                "Quantities and weights per shipment.",
                ["packing list", "gross weight", "net weight", "carton", "pallet"]),
        DocType("quote", "Quotes",
                "Offered price and lead time before commitment.",
                ["quotation", "quote no", "quote number", "rfq", "price quote"]),
        DocType("supplier_financials", "Supplier financial statements",
                "How likely a vendor is to still be there next year.",
                ["balance sheet", "income statement", "financial statement", "current ratio"],
                ["third_party_failure"], True),
        DocType("technical_spec", "Technical specifications",
                "What the part is, for classification.",
                ["specification", "datasheet", "technical data", "dimensions", "tolerance"]),
    ],
    schema={
        "doc_type": "one of the document types listed",
        "supplier_name": "the vendor or manufacturer, string or null",
        "country": "country of origin or manufacture, string or null",
        "total_value_usd": "total order or invoice value in USD, number or null",
        "hs_code": "HS or HTSUS classification, string or null",
        "lead_time_days": "quoted or actual lead time in days, number or null",
        "sole_source": "true only if the document states single or sole sourcing",
        "days_of_cover": "days of inventory cover if stated, number or null",
        "confidence": "0.0 to 1.0",
    },
    tables=[
        TableMap(
            question="vendors", key="supplier_name",
            columns={
                "name": ("supplier_name", FIRST),
                "country": ("country", FIRST),
                "annual_spend": ("total_value_usd", SUM),
                "lead_time_days": ("lead_time_days", MAX),
                "sole_source": ("sole_source", ANY),
            },
            needs=("total_value_usd", "lead_time_days"),
        ),
        TableMap(
            question="product_lines", key="hs_code",
            columns={
                "hs_chapter": ("hs_code", FIRST),
                "origin": ("country", FIRST),
                "annual_import_value": ("total_value_usd", SUM),
                "days_of_cover": ("days_of_cover", MAX),
            },
            label_from=("hs_code", "country"),
            needs=("total_value_usd",),
        ),
    ],
    row_hints=(
        "a purchase order or invoice line: one record per line, with supplier_name and total_value_usd",
        "a vendor spend schedule: one record per supplier",
        "a customs entry: one record per classification line, with hs_code",
    ),
)


# ---------------------------------------------------------------------------
# Clinical research: protocols, sponsors and the systems holding PHI.
# ---------------------------------------------------------------------------

CLINICAL = DocProfile(
    industry="clinical_research",
    role="clinical operations analyst",
    doc_types=[
        DocType("clinical_trial_agreement", "Clinical Trial Agreements",
                "Sponsor, study and contracted value.",
                ["clinical trial agreement", "master service agreement", "work order",
                 "sponsor", "budget", "cta", "statement of work"],
                ["counterparty_concentration"], True),
        DocType("protocol", "Protocols and Synopses",
                "Phase, indication and target enrollment.",
                ["protocol", "synopsis", "inclusion criteria", "exclusion criteria",
                 "primary endpoint", "phase i", "phase ii", "phase iii", "sample size"],
                ["schedule_disruption"], True),
        DocType("enrollment_report", "Enrollment Reports",
                "Screened, enrolled and randomized against plan.",
                ["enrollment", "recruitment", "randomized", "screened", "screen failure",
                 "subjects enrolled", "accrual"],
                ["schedule_disruption"], True),
        DocType("site_roster", "Site Rosters",
                "Which sites are activated and who the investigators are.",
                ["site list", "site roster", "investigator", "site activation",
                 "principal investigator", "site id"],
                ["site_disruption"]),
        DocType("monitoring_report", "Monitoring and Deviation Logs",
                "Protocol deviations and monitoring findings.",
                ["monitoring visit", "deviation", "protocol deviation", "finding",
                 "capa", "corrective action", "audit report"],
                ["regulatory_compliance_failure"], True),
        DocType("data_agreement", "Data and Vendor Agreements",
                "Which systems hold patient data and who runs them.",
                ["data processing agreement", "business associate", "baa", "edc",
                 "electronic data capture", "hosting", "records", "phi", "vendor agreement"],
                ["cyber_loss"]),
        DocType("safety_report", "Safety Reports",
                "Adverse events and reporting timelines.",
                ["adverse event", "serious adverse event", "sae", "safety report",
                 "pharmacovigilance", "susar"],
                ["regulatory_compliance_failure"]),
    ],
    schema={
        "doc_type": "one of the document types listed",
        "trial_name": "study or protocol name or number, string or null",
        "sponsor_name": "the sponsor funding the study, string or null",
        "phase": "one of Phase I, Phase II, Phase III, Phase IV, or null",
        "therapeutic_area": (
            "one of Oncology, Rare disease, Neurology, Psychiatry, Cardiology, Endocrine, "
            "Respiratory, Infectious disease, Ophthalmology, Dermatology, Vaccines, or null"
        ),
        "contract_value_usd": "annual or total contracted value in USD, number or null",
        "target_enrollment": "planned number of subjects, number or null",
        "enrolled_to_date": "subjects enrolled so far, number or null",
        "sites_activated": "number of activated sites, number or null",
        "deviations_count": "protocol deviations reported, number or null",
        "system_name": "name of a system holding trial or patient data, string or null",
        "record_count": "number of patient or subject records held, number or null",
        "holds_phi": "true only if the document states the system holds patient data",
        "vendor_hosted": "true only if the document states a third party hosts it",
        "confidence": "0.0 to 1.0",
    },
    tables=[
        TableMap(
            question="trials", key="trial_name",
            columns={
                "name": ("trial_name", FIRST),
                "phase": ("phase", FIRST),
                "therapeutic_area": ("therapeutic_area", FIRST),
                "sponsor": ("sponsor_name", FIRST),
                "annual_value": ("contract_value_usd", MAX),
                "target_enrollment": ("target_enrollment", MAX),
                "enrolled_to_date": ("enrolled_to_date", MAX),
                "sites_activated": ("sites_activated", MAX),
            },
            needs=("contract_value_usd", "target_enrollment", "enrolled_to_date",
                   "phase", "therapeutic_area"),
            alt_keys=("sponsor_name",),
        ),
        TableMap(
            question="data_systems", key="system_name",
            columns={
                "name": ("system_name", FIRST),
                "records": ("record_count", MAX),
                "holds_phi": ("holds_phi", ANY),
                "vendor_hosted": ("vendor_hosted", ANY),
            },
            # A vendor register names the systems and prices them without ever
            # stating a record count, so a contract value is enough to know the
            # system exists. The count then falls back and is flagged.
            needs=("record_count", "contract_value_usd", "holds_phi"),
        ),
    ],
    row_hints=(
        "an enrollment or study status table: one record per study, with trial_name, "
        "phase, therapeutic_area, target_enrollment and enrolled_to_date",
        "a sponsor revenue or concentration schedule: one record per SPONSOR, with "
        "sponsor_name and contract_value_usd, ignoring any total row",
        "a vendor, system or data register: one record per SYSTEM, with system_name, "
        "record_count, holds_phi and vendor_hosted",
        "a site roster: sites_activated on the study it belongs to",
    ),
)


# ---------------------------------------------------------------------------
# Automotive and manufacturing.
# ---------------------------------------------------------------------------

AUTOMOTIVE = DocProfile(
    industry="automotive_manufacturing",
    role="manufacturing procurement and quality analyst",
    doc_types=[
        DocType("purchase_order", "Purchase Orders and Releases",
                "Part, supplier and committed spend.",
                ["purchase order", "release", "po number", "part number", "schedule agreement"],
                ["third_party_failure"], True),
        DocType("supplier_agreement", "Supplier Agreements",
                "Terms, sourcing status and lead time.",
                ["supply agreement", "long term agreement", "lta", "sole source",
                 "single source", "terms and conditions"],
                ["third_party_failure"], True),
        DocType("quality_report", "PPAP and Quality Reports",
                "Incoming defect rate per part.",
                ["ppap", "ppm", "parts per million", "defect", "reject rate",
                 "quality report", "8d", "scorecard"],
                ["product_recall"], True),
        DocType("warranty_report", "Warranty and Recall Records",
                "Claims and campaigns by programme.",
                ["warranty", "claim rate", "recall", "campaign", "service action",
                 "field action"],
                ["product_recall"]),
        DocType("program_plan", "Programme and Build Plans",
                "Volumes, content value and launch stage.",
                ["build plan", "volume", "programme", "program", "launch", "sop",
                 "start of production", "takt"],
                ["product_recall"]),
        DocType("commodity_contract", "Commodity Contracts",
                "What is bought and how much is already fixed.",
                ["hedge", "fixed price", "commodity", "steel", "aluminium", "aluminum",
                 "resin", "copper", "index"],
                ["input_cost_shock"]),
    ],
    schema={
        "doc_type": "one of the document types listed",
        "part_name": "the part or component, string or null",
        "supplier_name": "the supplier, string or null",
        "total_value_usd": "committed or invoiced spend in USD, number or null",
        "lead_time_days": "lead time in days, number or null",
        "ppm_defect": "defect rate in parts per million, number or null",
        "single_source": "true only if the document states single or sole sourcing",
        "program_name": "vehicle programme or product line, string or null",
        "annual_units": "annual build volume, number or null",
        "content_value_usd": "content value at risk per unit in USD, number or null",
        "launch_stage": "one of Pre-launch, Ramp, Mature, End of life, or null",
        "material": (
            "one of steel, aluminium, copper, resin, electronics, rare_earth, rubber, "
            "glass, energy, freight, other, or null"
        ),
        "hedged_share": "share of that spend already fixed, decimal 0 to 1, or null",
        "confidence": "0.0 to 1.0",
    },
    tables=[
        TableMap(
            question="parts", key="part_name",
            columns={
                "part": ("part_name", FIRST),
                "supplier": ("supplier_name", FIRST),
                "annual_spend": ("total_value_usd", SUM),
                "lead_time_days": ("lead_time_days", MAX),
                "ppm_defect": ("ppm_defect", MAX),
                "single_source": ("single_source", ANY),
            },
            needs=("total_value_usd", "lead_time_days", "ppm_defect"),
        ),
        TableMap(
            question="programs", key="program_name",
            columns={
                "name": ("program_name", FIRST),
                "annual_units": ("annual_units", MAX),
                "content_value": ("content_value_usd", MAX),
                "launch_stage": ("launch_stage", FIRST),
            },
            needs=("annual_units", "content_value_usd"),
        ),
        TableMap(
            question="commodities", key="material",
            columns={
                "material": ("material", FIRST),
                "annual_spend": ("total_value_usd", SUM),
                "hedged_share": ("hedged_share", MAX),
            },
            needs=("total_value_usd",),
        ),
    ],
)


# ---------------------------------------------------------------------------
# Property and data analytics.
# ---------------------------------------------------------------------------

PROPERTY = DocProfile(
    industry="property_data",
    role="data licensing and vendor analyst",
    doc_types=[
        DocType("data_license", "Data Licence Agreements",
                "Which feeds you buy, from whom, at what cost.",
                ["data license", "licence agreement", "data agreement", "feed",
                 "subscription", "api access", "redistribution"],
                ["third_party_failure"], True),
        DocType("vendor_invoice", "Vendor Invoices",
                "Annual cost per upstream source.",
                ["invoice", "annual fee", "subscription fee", "renewal invoice"],
                ["third_party_failure"], True),
        DocType("client_contract", "Client Contracts",
                "Contract value and renewal dates.",
                ["master service agreement", "order form", "client agreement",
                 "renewal", "term", "annual contract value", "acv"],
                ["counterparty_concentration"], True),
        DocType("model_validation", "Model Validation Reports",
                "Accuracy, volume and how output is used.",
                ["validation", "backtest", "holdout", "mae", "mape", "accuracy",
                 "model performance", "error rate"],
                ["model_error"], True),
        DocType("privacy_record", "Privacy and Data Maps",
                "Where records sit and under which regime.",
                ["data processing agreement", "privacy", "gdpr", "ccpa", "bipa",
                 "records of processing", "data inventory", "jurisdiction"],
                ["cyber_loss"]),
    ],
    schema={
        "doc_type": "one of the document types listed",
        "source_name": "the upstream data source or feed, string or null",
        "provider_name": "the company providing it, string or null",
        "criticality": "one of Core, Important, Nice to have, or null",
        "has_fallback": "true only if the document states an alternate or failover exists",
        "annual_cost_usd": "annual cost in USD, number or null",
        "client_name": "the paying client, string or null",
        "contract_value_usd": "annual contract value in USD, number or null",
        "months_to_renewal": "months until renewal, number or null",
        "model_name": "the model or product, string or null",
        "decisions_per_month": "volume of decisions or scores per month, number or null",
        "error_rate": "material error rate as a decimal, number or null",
        "usage": "one of Advisory only, Reviewed before use, Acted on automatically, or null",
        "jurisdiction": (
            "one of US general, California, Illinois, New York, EU or UK, Canada, Other, or null"
        ),
        "record_count": "number of records held, number or null",
        "confidence": "0.0 to 1.0",
    },
    tables=[
        TableMap(
            question="data_sources", key="source_name",
            columns={
                "name": ("source_name", FIRST),
                "provider": ("provider_name", FIRST),
                "criticality": ("criticality", FIRST),
                "annual_cost": ("annual_cost_usd", SUM),
                "has_fallback": ("has_fallback", ANY),
            },
            needs=("annual_cost_usd",),
        ),
        TableMap(
            question="clients", key="client_name",
            columns={
                "name": ("client_name", FIRST),
                "annual_value": ("contract_value_usd", MAX),
                "months_to_renewal": ("months_to_renewal", MAX),
            },
            needs=("contract_value_usd",),
        ),
        TableMap(
            question="models", key="model_name",
            columns={
                "name": ("model_name", FIRST),
                "decisions_per_month": ("decisions_per_month", MAX),
                "usage": ("usage", FIRST),
                "error_rate": ("error_rate", MAX),
            },
            needs=("decisions_per_month", "error_rate"),
        ),
        TableMap(
            question="data_holdings", key="jurisdiction",
            columns={
                "jurisdiction": ("jurisdiction", FIRST),
                "records": ("record_count", SUM),
            },
            needs=("record_count",),
        ),
    ],
)


# ---------------------------------------------------------------------------
# Wealth management.
# ---------------------------------------------------------------------------

WEALTH = DocProfile(
    industry="wealth_management",
    role="wealth management operations analyst",
    doc_types=[
        DocType("advisory_agreement", "Advisory Agreements",
                "Client, assets and fee schedule.",
                ["investment advisory agreement", "advisory agreement", "fee schedule",
                 "basis points", "bps", "management fee", "client agreement"],
                ["counterparty_concentration"], True),
        DocType("custodial_statement", "Custodial and Performance Statements",
                "Assets under management per relationship.",
                ["statement", "custodian", "portfolio", "account value", "market value",
                 "assets under management", "aum", "holdings"],
                ["counterparty_concentration"], True),
        DocType("advisor_record", "Advisor and Succession Records",
                "Who owns which book, and what happens when they leave.",
                ["advisor", "adviser", "producer", "book of business", "succession",
                 "retirement", "transition plan", "registered representative"],
                ["reputational_event"], True),
        DocType("form_adv", "Form ADV and Registration",
                "Registration type, which sets the examination regime.",
                ["form adv", "sec registered", "state registered", "finra",
                 "broker-dealer", "investment adviser", "crd", "registration"],
                ["regulatory_compliance_failure"], True),
        DocType("platform_invoice", "Platform Invoices",
                "Custody, accounting and planning systems you depend on.",
                ["invoice", "subscription", "platform", "custody fee", "software",
                 "annual license"],
                ["third_party_failure"]),
        DocType("compliance_report", "Compliance and Exam Reports",
                "Findings, deficiencies and remediation.",
                ["compliance", "examination", "deficiency letter", "annual review",
                 "code of ethics", "audit"],
                ["regulatory_compliance_failure"]),
    ],
    schema={
        "doc_type": "one of the document types listed",
        "client_name": "the client relationship, string or null",
        "aum_usd": "assets under management for that relationship in USD, number or null",
        "fee_bps": "advisory fee in basis points, number or null",
        "market_linked_share": "share of that revenue tied to market levels, decimal, or null",
        "advisor_name": "the advisor who owns the relationship, string or null",
        "book_aum_usd": "that advisor's total book in USD, number or null",
        "client_count": "how many clients that advisor serves, number or null",
        "retiring_5y": "true only if the document states retirement within five years",
        "has_successor": "true only if the document names a successor",
        "platform_name": "a platform or system the practice runs on, string or null",
        "platform_function": (
            "one of Custodian, Portfolio accounting, CRM, Planning, Reporting, or null"
        ),
        "annual_cost_usd": "annual platform cost in USD, number or null",
        "has_fallback": "true only if the document states an alternate exists",
        "registration": (
            "one of RIA (SEC), RIA (state), Broker-dealer (FINRA), Dual registrant, "
            "Bank or trust, or null"
        ),
        "confidence": "0.0 to 1.0",
    },
    tables=[
        TableMap(
            question="relationships", key="client_name",
            columns={
                "name": ("client_name", FIRST),
                "aum": ("aum_usd", MAX),
                "fee_bps": ("fee_bps", MAX),
                "market_linked_share": ("market_linked_share", MAX),
            },
            needs=("aum_usd",),
        ),
        TableMap(
            question="advisors", key="advisor_name",
            columns={
                "name": ("advisor_name", FIRST),
                "book_aum": ("book_aum_usd", MAX),
                "clients": ("client_count", MAX),
                "retiring_5y": ("retiring_5y", ANY),
                "has_successor": ("has_successor", ANY),
            },
            needs=("book_aum_usd",),
        ),
        TableMap(
            question="platforms", key="platform_name",
            columns={
                "name": ("platform_name", FIRST),
                "function": ("platform_function", FIRST),
                "annual_cost": ("annual_cost_usd", SUM),
                "has_fallback": ("has_fallback", ANY),
            },
            needs=("annual_cost_usd",),
        ),
    ],
)


PROFILES: dict[str, DocProfile] = {
    p.industry: p for p in (DISTRIBUTION, CLINICAL, AUTOMOTIVE, PROPERTY, WEALTH)
}

DEFAULT_INDUSTRY = "industrial_distribution"


def get_profile(industry: str | None) -> DocProfile:
    return PROFILES.get(industry or "", PROFILES[DEFAULT_INDUSTRY])

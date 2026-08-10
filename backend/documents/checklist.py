"""Document completeness checklist.

Which paperwork a risk assessment draws on, what each one unlocks, and how the
assessment degrades when one is missing. The list is per industry: a CRO should
be asked for protocols and enrollment reports, not bills of lading.
"""
from __future__ import annotations

from .profiles import get_profile


def docs_for(industry: str | None) -> list[dict]:
    """The document set this industry actually has."""
    return [
        {
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "unlocks": d.unlocks,
            "required": d.required,
        }
        for d in get_profile(industry).doc_types
    ]

# id, name, description, unlocks (model keys), required
REQUIRED_DOCS = [
    {
        "id": "purchase_order",
        "name": "Purchase Orders",
        "description": "Supplier, quantities and committed spend per line.",
        "unlocks": ["supplier_concentration", "supplier_health"],
        "required": True,
    },
    {
        "id": "commercial_invoice",
        "name": "Commercial Invoices",
        "description": "Import value, unit price and country of origin.",
        "unlocks": ["tariff", "country", "price"],
        "required": True,
    },
    {
        "id": "packing_list",
        "name": "Packing Lists",
        "description": "Quantities and weights per shipment.",
        "unlocks": ["delivery"],
        "required": False,
    },
    {
        "id": "bill_of_lading",
        "name": "Bills of Lading",
        "description": "Carrier, route and ship/arrival dates for lead-time history.",
        "unlocks": ["delivery"],
        "required": True,
    },
    {
        "id": "customs_paperwork",
        "name": "Customs paperwork",
        "description": "HS codes and duty rates for tariff exposure.",
        "unlocks": ["tariff", "country"],
        "required": True,
    },
    {
        "id": "quote",
        "name": "Quotes",
        "description": "Alternative-supplier pricing for reroute analysis.",
        "unlocks": ["tariff"],
        "required": False,
    },
    {
        "id": "technical_spec",
        "name": "Technical specifications",
        "description": "Product specs to match substitute sources.",
        "unlocks": [],
        "required": False,
    },
    {
        "id": "supplier_financials",
        "name": "Supplier financial statements",
        "description": "Leverage, liquidity and margins for supplier credit risk.",
        "unlocks": ["supplier_health"],
        "required": True,
    },
]

_BY_ID = {d["id"]: d for d in REQUIRED_DOCS}


def build_checklist(detected_ids: list[str], industry: str | None = None) -> list[dict]:
    """For each expected document, whether it's present and what its absence
    costs the assessment."""
    detected = set(detected_ids)
    out = []
    for d in docs_for(industry):
        present = d["id"] in detected
        out.append({
            **d,
            "present": present,
            "status": "present" if present else ("missing" if d["required"] else "optional"),
            "impact": (
                None if present
                else f"{', '.join(d['unlocks']) or 'no models'} will run on defaults until provided"
            ),
        })
    return out


def coverage(detected_ids: list[str], industry: str | None = None) -> dict:
    detected = set(detected_ids)
    required = [d for d in docs_for(industry) if d["required"]]
    have = [d for d in required if d["id"] in detected]
    return {
        "required_total": len(required),
        "required_present": len(have),
        "pct": round(len(have) / len(required), 3) if required else 1.0,
        "missing_required": [d["name"] for d in required if d["id"] not in detected],
    }

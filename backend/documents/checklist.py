"""Document completeness checklist.

Defines the trade documents an industrial-equipment-distributor risk assessment
draws on, what each one unlocks, and how the assessment degrades when one is
missing. The checklist tells the user exactly what to add and why.
"""
from __future__ import annotations

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


def build_checklist(detected_ids: list[str]) -> list[dict]:
    """For each expected document, whether it's present and what its absence
    costs the assessment."""
    detected = set(detected_ids)
    out = []
    for d in REQUIRED_DOCS:
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


def coverage(detected_ids: list[str]) -> dict:
    detected = set(detected_ids)
    required = [d for d in REQUIRED_DOCS if d["required"]]
    have = [d for d in required if d["id"] in detected]
    return {
        "required_total": len(required),
        "required_present": len(have),
        "pct": round(len(have) / len(required), 3) if required else 1.0,
        "missing_required": [d["name"] for d in required if d["id"] not in detected],
    }

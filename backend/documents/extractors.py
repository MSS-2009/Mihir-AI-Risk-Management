"""Document text extraction, classification, and field extraction.

The AI classifies each document and pulls structured fields; those fields feed
the validated models. When no API key is present we fall back to filename/keyword
classification and return the text with a clear note, extraction degrades, the
pipeline does not break.
"""
from __future__ import annotations

import io
import json
import re

from llm import MODEL, client, extract_text

from .profiles import get_profile

# Keyword -> checklist doc id, for the no-AI fallback classifier.
_KEYWORDS = {
    "purchase_order": ["purchase order", "p.o.", "po number", "po #", "order confirmation"],
    "commercial_invoice": ["commercial invoice", "invoice no", "invoice number", "bill to", "sold to"],
    "packing_list": ["packing list", "gross weight", "net weight", "carton", "pallet"],
    "bill_of_lading": ["bill of lading", "b/l no", "shipper", "consignee", "vessel", "port of loading"],
    "customs_paperwork": ["customs", "hs code", "harmonized", "entry summary", "7501", "duty rate", "tariff"],
    "quote": ["quotation", "quote no", "quote number", "rfq", "price quote"],
    "technical_spec": ["specification", "datasheet", "technical data", "dimensions", "tolerance"],
    "supplier_financials": ["balance sheet", "income statement", "financial statement", "current ratio", "shareholders equity"],
}

_EXTRACTION_SCHEMA = {
    "doc_type": "one of: " + ", ".join(_KEYWORDS.keys()),
    "supplier_name": "string or null",
    "country": "country name or null",
    "total_value_usd": "number or null",
    "unit_price_usd": "number or null",
    "quantity": "number or null",
    "hs_code": "string or null",
    "tariff_rate": "decimal fraction (e.g. 0.25) or null",
    "lead_time_days": "number or null",
    "financials": "object with debt_to_equity, current_ratio, interest_coverage, profit_margin (decimals) or null",
    "confidence": "0.0 to 1.0",
}


def read_text(filename: str, data: bytes) -> str:
    """Best-effort text from a PDF, CSV, or plain-text upload."""
    name = (filename or "").lower()
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as e:  # pragma: no cover - malformed pdf
            return f"[could not read PDF: {e}]"
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _keyword_classify(filename: str, text: str, industry: str | None = None) -> str:
    """Classify against the paperwork THIS industry actually has.

    A clinical trial agreement scored against purchase-order keywords comes back
    as a commercial invoice, which is worse than refusing: it looks like the
    product understood the document and found nothing in it.
    """
    profile = get_profile(industry)
    hay = f"{filename}\n{text}".lower()
    best, best_hits = profile.default_doc_type, 0
    for doc_id, kws in profile.keywords.items():
        hits = sum(1 for kw in kws if kw in hay)
        if hits > best_hits:
            best, best_hits = doc_id, hits
    return best


def _fallback_extract(filename: str, text: str, industry: str | None = None) -> dict:
    doc_type = _keyword_classify(filename, text, industry)
    # Light regex hints so the no-AI path still surfaces something useful.
    money = re.findall(r"\$\s?([\d,]{4,})", text)
    total = None
    if money:
        try:
            total = max(float(m.replace(",", "")) for m in money)
        except ValueError:
            total = None
    fields = {k: None for k in get_profile(industry).schema}
    fields["doc_type"] = doc_type
    fields["confidence"] = 0.35
    for money_field in ("total_value_usd", "contract_value_usd", "aum_usd", "annual_cost_usd"):
        if money_field in fields:
            fields[money_field] = total
            break
    return {
        **fields,
        "records": [dict(fields)],
        "extraction": "keyword-fallback",
        "note": "AI field extraction unavailable, classification and coarse values only.",
    }


def _salvage(raw: str, filename: str, text: str, industry: str | None) -> dict:
    """Pull whole `{...}` records out of a truncated JSON reply."""
    records, depth, start = [], 0, None
    body = raw[raw.find("["):] if "[" in raw else ""
    for i, ch in enumerate(body):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    records.append(json.loads(body[start:i + 1]))
                except json.JSONDecodeError:
                    pass
                start = None
    if not records:
        raise json.JSONDecodeError("nothing salvageable", raw, 0)
    return {
        "doc_type": _keyword_classify(filename, text, industry),
        "confidence": 0.6,
        "records": records,
        "note": f"reply was truncated; kept {len(records)} complete records",
    }


def classify_and_extract(filename: str, text: str, industry: str | None = None) -> dict:
    """Classify a document and extract normalized fields. AI-driven when a key is
    present, deterministic keyword fallback otherwise.

    Both the document types and the fields worth pulling come from the industry
    profile, so a CRO gets asked about phase and enrollment rather than HS codes.
    """
    profile = get_profile(industry)
    if not text.strip():
        return {**_fallback_extract(filename, "", industry), "note": "Empty or unreadable document."}
    if client is None:
        return _fallback_extract(filename, text, industry)
    types = ", ".join(d.id for d in profile.doc_types)
    hints = (
        "In this industry, expect:\n"
        + "\n".join(f"  - {h}" for h in profile.row_hints)
        + "\n\n"
    ) if profile.row_hints else ""
    prompt = (
        f"You are a {profile.role}. Classify this document and extract the fields "
        "below.\n\n"
        "Real operating documents are usually SUMMARY REPORTS: a revenue schedule "
        "lists every sponsor, an enrollment report lists every study, a vendor "
        "register lists every system. Return ONE RECORD PER ROW of any such table, "
        "not one record for the whole document. A document describing a single "
        "entity returns a single record. Never emit a record for a total, "
        "subtotal, weighted-average or portfolio-wide row.\n\n"
        f"{hints}"
        "Return ONLY a JSON object of the form "
        '{"doc_type": "...", "confidence": 0.0, "records": [ {...}, {...} ]}. '
        "Use null when a field is not present in that row. Do not guess values that "
        "are not in the text, and do not carry a portfolio total into a row. "
        "Booleans are true only when the document states them. Normalise a phase "
        'written as "III" to "Phase III".\n\n'
        f"doc_type must be one of: {types}\n\n"
        f"Fields for each record:\n{json.dumps(profile.schema, indent=2)}\n\n"
        f"Document (filename: {filename}):\n{text[:9000]}"
    )
    try:
        m = client.messages.create(
            # A six-sponsor revenue schedule is six records of a dozen fields.
            # At 1000 tokens the JSON was cut mid-array, failed to parse, and
            # fell all the way back to keyword matching, which is why real
            # summary reports read as one empty record.
            model=MODEL, max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = extract_text(m)
        raw = raw[raw.find("{"): raw.rfind("}") + 1]
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Salvage the records that did arrive intact rather than throwing
            # away a whole document because the last one was clipped.
            data = _salvage(raw, filename, text, industry)
        data.setdefault("doc_type", _keyword_classify(filename, text, industry))
        if data["doc_type"] not in profile.keywords:
            data["doc_type"] = _keyword_classify(filename, text, industry)
        # A document may describe many entities. Older single-record replies are
        # still accepted so nothing depends on the model's shape.
        records = data.get("records")
        if not isinstance(records, list) or not records:
            records = [{k: v for k, v in data.items()
                        if k not in ("doc_type", "confidence", "records")}]
        data["records"] = [r for r in records if isinstance(r, dict)]
        data["extraction"] = "ai"
        return data
    except Exception as e:
        return {**_fallback_extract(filename, text, industry), "note": f"AI extraction failed ({e}); used fallback."}


def _map_to_params(extracts: list[dict]) -> dict:
    """Fold extracted fields into per-model parameter overrides. Conservative:
    only sets a param when the source field is actually present."""
    params: dict = {}
    fin = next((e["financials"] for e in extracts if e.get("financials")), None)
    if fin:
        params["supplier_health"] = {
            k: fin[k] for k in
            ("debt_to_equity", "current_ratio", "interest_coverage", "profit_margin")
            if fin.get(k) is not None
        }
    tariff = {}
    inv = next((e for e in extracts if e.get("total_value_usd")), None)
    if inv:
        tariff["annual_import_value"] = inv["total_value_usd"]
    rate = next((e["tariff_rate"] for e in extracts if e.get("tariff_rate") is not None), None)
    if rate is not None:
        tariff["current_tariff_rate"] = rate
    if tariff:
        params["tariff"] = tariff
    return params


def ingest_files(files: list[tuple[str, bytes]], industry: str | None = None) -> dict:
    """Full ingestion: text -> classify+extract per file -> params + detected set."""
    documents = []
    for filename, data in files:
        text = read_text(filename, data)
        ext = classify_and_extract(filename, text, industry)
        records = ext.get("records") or [{}]
        documents.append({
            "filename": filename,
            "doc_type": ext.get("doc_type"),
            "confidence": ext.get("confidence"),
            "extraction": ext.get("extraction"),
            # `fields` stays the first record so single-entity callers are
            # unchanged; `records` is every row the document described.
            "fields": {k: v for k, v in (records[0] or {}).items()
                       if k not in ("doc_type", "confidence", "extraction", "note", "records")},
            "records": records,
            "record_count": len(records),
            "note": ext.get("note"),
            "chars": len(text),
        })
    extracts = [
        {**d["fields"], "doc_type": d["doc_type"]} for d in documents
    ]
    detected = sorted({d["doc_type"] for d in documents if d["doc_type"]})
    return {
        "documents": documents,
        "detected_doc_ids": detected,
        "extracted_params": _map_to_params(extracts),
    }

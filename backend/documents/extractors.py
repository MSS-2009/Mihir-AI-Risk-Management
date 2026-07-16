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


def _keyword_classify(filename: str, text: str) -> str:
    hay = f"{filename}\n{text}".lower()
    best, best_hits = "commercial_invoice", 0
    for doc_id, kws in _KEYWORDS.items():
        hits = sum(1 for kw in kws if kw in hay)
        if hits > best_hits:
            best, best_hits = doc_id, hits
    return best


def _fallback_extract(filename: str, text: str) -> dict:
    doc_type = _keyword_classify(filename, text)
    # Light regex hints so the no-AI path still surfaces something useful.
    money = re.findall(r"\$\s?([\d,]{4,})", text)
    total = None
    if money:
        try:
            total = max(float(m.replace(",", "")) for m in money)
        except ValueError:
            total = None
    return {
        "doc_type": doc_type,
        "supplier_name": None,
        "country": None,
        "total_value_usd": total,
        "unit_price_usd": None,
        "quantity": None,
        "hs_code": None,
        "tariff_rate": None,
        "lead_time_days": None,
        "financials": None,
        "confidence": 0.35,
        "extraction": "keyword-fallback",
        "note": "AI field extraction unavailable, classification and coarse values only.",
    }


def classify_and_extract(filename: str, text: str) -> dict:
    """Classify a document and extract normalized fields. AI-driven when a key is
    present, deterministic keyword fallback otherwise."""
    if not text.strip():
        return {**_fallback_extract(filename, ""), "note": "Empty or unreadable document."}
    if client is None:
        return _fallback_extract(filename, text)
    prompt = (
        "You are a trade-document analyst. Classify this document and extract the "
        "fields below. Return ONLY a JSON object, no prose. Use null when a field "
        "is not present. Do not guess values that are not in the text.\n\n"
        f"Fields:\n{json.dumps(_EXTRACTION_SCHEMA, indent=2)}\n\n"
        f"Document (filename: {filename}):\n{text[:6000]}"
    )
    try:
        m = client.messages.create(
            model=MODEL, max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = extract_text(m)
        raw = raw[raw.find("{"): raw.rfind("}") + 1]
        data = json.loads(raw)
        data.setdefault("doc_type", _keyword_classify(filename, text))
        if data["doc_type"] not in _KEYWORDS:
            data["doc_type"] = _keyword_classify(filename, text)
        data["extraction"] = "ai"
        return data
    except Exception as e:
        return {**_fallback_extract(filename, text), "note": f"AI extraction failed ({e}); used fallback."}


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


def ingest_files(files: list[tuple[str, bytes]]) -> dict:
    """Full ingestion: text -> classify+extract per file -> params + detected set."""
    documents = []
    for filename, data in files:
        text = read_text(filename, data)
        ext = classify_and_extract(filename, text)
        documents.append({
            "filename": filename,
            "doc_type": ext.get("doc_type"),
            "confidence": ext.get("confidence"),
            "extraction": ext.get("extraction"),
            "fields": {k: v for k, v in ext.items()
                       if k not in ("doc_type", "confidence", "extraction", "note")},
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

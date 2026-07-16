"""Document flow tests, classification, checklist coverage, and signals, all on
the deterministic no-AI fallback path."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from documents.checklist import build_checklist, coverage  # noqa: E402
from documents.extractors import _keyword_classify, ingest_files  # noqa: E402
from documents.signals import scan_signals  # noqa: E402

_INVOICE = b"COMMERCIAL INVOICE\nInvoice No: 88213\nSold to: Acme Distribution\nTotal: $ 4,200,000\nCountry of origin: China"
_BOL = b"BILL OF LADING\nShipper: Jiangsu Machine Works\nConsignee: Acme\nVessel: MV Orient\nPort of loading: Shanghai"
_FIN = b"BALANCE SHEET\nShareholders equity ...\nCurrent ratio 1.3\nincome statement\nnet margin"


def test_keyword_classification():
    assert _keyword_classify("inv.pdf", _INVOICE.decode()) == "commercial_invoice"
    assert _keyword_classify("bol.txt", _BOL.decode()) == "bill_of_lading"
    assert _keyword_classify("fin.txt", _FIN.decode()) == "supplier_financials"


def test_ingest_detects_and_extracts():
    out = ingest_files([("invoice.txt", _INVOICE), ("bol.txt", _BOL), ("fin.txt", _FIN)])
    assert set(out["detected_doc_ids"]) >= {"commercial_invoice", "bill_of_lading", "supplier_financials"}
    # coarse currency extraction on the fallback path
    inv = next(d for d in out["documents"] if d["doc_type"] == "commercial_invoice")
    assert inv["fields"]["total_value_usd"] == 4200000.0


def test_checklist_flags_missing_required():
    detected = ["commercial_invoice", "bill_of_lading"]
    cl = build_checklist(detected)
    missing_required = [c for c in cl if c["status"] == "missing"]
    assert any(c["id"] == "supplier_financials" for c in missing_required)
    cov = coverage(detected)
    assert cov["required_present"] < cov["required_total"]
    assert "Supplier financial statements" in cov["missing_required"]


def test_signals_flag_watchlist_country():
    sig = scan_signals([{"country": "Russia"}, {"country": "China"}])
    types = {s["subject"]: s for s in sig["signals"]}
    assert types["Russia"]["severity"] == "critical"
    assert any(s["type"] == "sanctions" and s["subject"] == "China" for s in sig["signals"])
    assert all(s["simulated"] is False for s in sig["signals"])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)

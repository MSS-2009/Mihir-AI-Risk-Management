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


def test_documents_are_read_in_their_own_industrys_vocabulary():
    """A clinical trial agreement is not a commercial invoice.

    The extractor used to know one world, so a CRO's paperwork came back
    classified as procurement with every field null. That is worse than
    refusing: it looks like the product read the document and found nothing.
    """
    from documents.extractors import _keyword_classify
    from documents.profiles import PROFILES, get_profile

    cta = (
        "CLINICAL TRIAL AGREEMENT\nSponsor: Meridian Biopharma\n"
        "Protocol: MB-401, Phase III study in NSCLC\nBudget: USD 22,400,000\n"
        "Planned Enrollment: 480 subjects"
    )
    po = (
        "PURCHASE ORDER\nPO Number: 2210\nVendor: Jiangsu Machine Works\n"
        "HS Code: 8481.80\nTotal Value: USD 1,184,000\nLead Time: 52 days"
    )

    assert _keyword_classify("cta.txt", cta, "clinical_research") == "clinical_trial_agreement"
    assert _keyword_classify("po.txt", po, "industrial_distribution") == "purchase_order"

    # every industry classifies into its OWN document set, never another's
    for industry, profile in PROFILES.items():
        own = set(profile.keywords)
        for text in (cta, po):
            assert _keyword_classify("f.txt", text, industry) in own, industry

    # and each asks for fields its operator would recognise
    assert "therapeutic_area" in get_profile("clinical_research").schema
    assert "hs_code" in get_profile("industrial_distribution").schema
    assert "hs_code" not in get_profile("clinical_research").schema
    assert "book_aum_usd" in get_profile("wealth_management").schema


def test_prefill_only_fills_tables_the_documents_can_evidence():
    """Rows are built from what a document actually says, and a stock is never
    summed: two statements for one client are that client's money twice."""
    from documents.prefill import build_prefill
    from industries import INDUSTRY_REGISTRY

    docs = [
        {"fields": {"trial_name": "MB-401", "sponsor_name": "Meridian Bio",
                    "phase": "Phase III", "therapeutic_area": "Oncology",
                    "contract_value_usd": 22_400_000, "target_enrollment": 480}},
        # the same trial described again: the value must not double
        {"fields": {"trial_name": "MB-401", "contract_value_usd": 22_400_000,
                    "enrolled_to_date": 267, "sites_activated": 29}},
    ]
    out = build_prefill("clinical_research", docs, INDUSTRY_REGISTRY["clinical_research"])
    trials = out["prefill"]["trials"]["rows"]
    assert len(trials) == 1, "one trial described twice is one trial"
    assert trials[0]["annual_value"] == 22_400_000
    assert trials[0]["enrolled_to_date"] == 267
    assert trials[0]["sponsor"] == "Meridian Bio"
    # a table nothing evidenced is reported rather than silently invented
    assert "data_systems" in out["skipped"]


def test_prefill_never_invents_an_impossible_row():
    """An unevidenced count is scaled to the row it lands in.

    A raw pack median put 240 subjects enrolled into a trial targeting 210,
    which read as zero enrollment risk on the trial with the least evidence.
    """
    from documents.prefill import build_prefill
    from industries import INDUSTRY_REGISTRY

    docs = [{"fields": {"trial_name": "CV-208", "sponsor_name": "Corvin",
                        "phase": "Phase II", "therapeutic_area": "Dermatology",
                        "contract_value_usd": 7_900_000, "target_enrollment": 210}}]
    out = build_prefill("clinical_research", docs, INDUSTRY_REGISTRY["clinical_research"])
    row = out["prefill"]["trials"]["rows"][0]
    assert row["enrolled_to_date"] < row["target_enrollment"], row
    assert "Enrolled to date" in out["prefill"]["trials"]["unevidenced"]

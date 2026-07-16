"""Document ingestion, the front door.

Users upload their trade documents; the AI extracts structured parameters and
audits the set for completeness. Extraction feeds the validated models; it never
computes risk itself. Extracted values are always surfaced for confirmation,
never silently trusted.
"""
from .checklist import REQUIRED_DOCS, build_checklist
from .extractors import classify_and_extract, ingest_files
from .signals import scan_signals

__all__ = [
    "REQUIRED_DOCS",
    "build_checklist",
    "classify_and_extract",
    "ingest_files",
    "scan_signals",
]

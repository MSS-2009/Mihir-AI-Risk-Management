"""Feature flags, the single source of truth for tier gating and infra scaffolds.

Per the product spec, gating must be one flag flip. Everything the free tier
ships is `True`; everything scaffolded-but-not-built is `False`. The frontend
reads these off `GET /` so the pricing page and gates never drift from the code.
"""
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Features:
    # --- Free tier: built now ---
    manual_input: bool = True
    document_upload: bool = True
    all_models: bool = True
    composite_correlation: bool = True
    ai_interpretation: bool = True
    multi_format_delivery: bool = True  # executive summary / one-pager / list

    # --- Growth tier ($1K/mo): scaffolded ---
    saved_history: bool = False
    benchmarking: bool = False
    scheduled_sync: bool = False
    pdf_export: bool = False
    slide_deck_export: bool = False

    # --- Continuous tier ($5K/mo): scaffolded ---
    live_connector: bool = False
    continuous_resim: bool = False
    alerting: bool = False
    local_agent: bool = False  # the "agent lives in the user's files" workflow

    # --- Infrastructure scaffolds ---
    aws_batch_compute: bool = False  # scale-out target; runs locally today
    auth: bool = False
    template_authoring: bool = False  # offline draft -> validate -> register pipeline


FEATURES = Features()


def features_public() -> dict:
    """Serializable view for the API + frontend gates."""
    return asdict(FEATURES)

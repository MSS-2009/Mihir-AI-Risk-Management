"""Domain groupings, kept in a neutral module to avoid import cycles between the
assessment orchestrator, the agents, and the graph."""

# Domains that contribute a loss distribution to the composite (expose a
# risk_summary). Tariff is a decision model, not a loss model.
LOSS_DOMAINS = [
    "supplier_health",
    "supplier_concentration",
    "country",
    "delivery",
    "price",
    "cyber",
]

# The multi-domain profile the dashboard opens with.
DEFAULT_DOMAINS = LOSS_DOMAINS

VALID_OUTPUT_FORMATS = ["executive_summary", "one_pager", "list"]

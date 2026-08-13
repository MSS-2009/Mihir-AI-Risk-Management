"""Read-only access to a customer's financial systems.

Nothing under `engines/` or `industries/` may import from this package. A test
enforces it, because the moment an engine knows a vendor's field names, adding a
connector stops being a mapping change and starts being a modelling change.
"""
from .base import (
    ConnectorProvider,
    LinkedAccount,
    ProviderCapabilities,
    SyncIncomplete,
)
from .fixtures import MIDMARKET_NETSUITE, PROFILES, SME_QUICKBOOKS, FixtureProvider, PlantedTruth

__all__ = [
    "ConnectorProvider",
    "LinkedAccount",
    "ProviderCapabilities",
    "SyncIncomplete",
    "FixtureProvider",
    "PlantedTruth",
    "PROFILES",
    "SME_QUICKBOOKS",
    "MIDMARKET_NETSUITE",
]

"""Persistence, identity and the audit log.

File-backed today, Supabase when the project exists. Nothing above this package
knows which is underneath, which is the point: the ingress endpoint, the MCP
bridge and the monitoring loop are all built and tested against real reads and
writes rather than against a stub that a database would later contradict.
"""
import os
from pathlib import Path

from .base import (
    AuditEntry,
    Organization,
    Store,
    Token,
    hash_token,
    new_token,
    now_iso,
)
from .files import FileStore

_store: Store | None = None


def get_store() -> Store:
    """The process-wide store. One line changes when Supabase arrives."""
    global _store
    if _store is None:
        _store = FileStore(os.getenv("AVENOIR_DATA_DIR") or None)
    return _store


def set_store(store: Store) -> None:
    """Swap the implementation. Used by tests and by the Supabase migration."""
    global _store
    _store = store


__all__ = [
    "Store", "FileStore", "Organization", "Token", "AuditEntry",
    "get_store", "set_store", "new_token", "hash_token", "now_iso", "Path",
]

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
from .supabase_store import SupabaseError, SupabaseStore

_store: Store | None = None


def get_store() -> Store:
    """The process-wide store.

    Supabase when it is configured, files otherwise. Selecting by configuration
    rather than by a flag means a deployment with credentials uses the database
    and local development keeps working with nothing installed, without either
    path being a special case in the code above.
    """
    global _store
    if _store is None:
        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if url and key:
            _store = SupabaseStore(url, key)
        else:
            _store = FileStore(os.getenv("AVENOIR_DATA_DIR") or None)
    return _store


def set_store(store: Store) -> None:
    """Swap the implementation. Used by tests and by the Supabase migration."""
    global _store
    _store = store


__all__ = [
    "Store", "FileStore", "SupabaseStore", "SupabaseError", "Organization", "Token", "AuditEntry",
    "get_store", "set_store", "new_token", "hash_token", "now_iso", "Path",
]

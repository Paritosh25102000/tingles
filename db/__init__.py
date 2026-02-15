"""
Database factory module.
Provides get_db() function that returns the appropriate database adapter
based on the db_backend configuration in secrets.toml.
"""

import streamlit as st
from typing import Optional
from .base import DatabaseAdapter


_db_instance: Optional[DatabaseAdapter] = None


def get_db() -> DatabaseAdapter:
    """
    Factory function to get database adapter based on environment configuration.

    Reads db_backend from st.secrets to determine which adapter to use:
    - "gsheets" (default): Use Google Sheets backend
    - "supabase": Use Supabase PostgreSQL backend

    The adapter is cached as a singleton for the duration of the session.

    Returns:
        DatabaseAdapter instance (either GoogleSheetsAdapter or SupabaseAdapter)
    """
    global _db_instance

    if _db_instance is not None:
        return _db_instance

    # Check which backend to use from secrets
    backend = st.secrets.get("db_backend", "gsheets").lower()

    if backend == "supabase":
        from .supabase_adapter import SupabaseAdapter
        _db_instance = SupabaseAdapter()
    else:
        # Default to Google Sheets
        from .gsheets_adapter import GoogleSheetsAdapter
        _db_instance = GoogleSheetsAdapter()

    return _db_instance


def reset_db():
    """
    Reset the database instance.
    Useful for testing or when switching backends.
    """
    global _db_instance
    _db_instance = None

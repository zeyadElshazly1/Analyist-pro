"""
Backward-compatibility shim for app.services.sql_engine.

All production callers do:
    from app.services.sql_engine import execute_query, get_schema, validate_sql

All logic lives in app.services.sql.
Do not add logic to this file.
"""
from app.services.sql import execute_query, get_schema, validate_sql  # noqa: F401

__all__ = ["execute_query", "get_schema", "validate_sql"]

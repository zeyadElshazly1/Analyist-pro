"""
SQL validator.

validate_sql(sql) — raises ValueError for non-SELECT statements.

Uses sqlglot AST parser to inspect every semicolon-separated statement.
Falls back to a regex check when sqlglot is unavailable so the service
still runs without the optional dependency.
"""
from __future__ import annotations

import re

_FORBIDDEN_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|COPY|PRAGMA|EXECUTE|TRUNCATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)
_ALLOWED_START_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
_COMMENT_SINGLE = re.compile(r"--[^\n]*")
_COMMENT_MULTI = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_comments(sql: str) -> str:
    sql = _COMMENT_SINGLE.sub("", sql)
    sql = _COMMENT_MULTI.sub("", sql)
    return sql.strip()


def _sqlglot_validate(sql: str) -> str | None:
    """Return error string if any statement is not a SELECT/WITH-SELECT, else None."""
    try:
        import sqlglot                      # noqa: PLC0415
        from sqlglot import expressions as exp  # noqa: PLC0415
    except ImportError:
        return None  # sqlglot unavailable — caller falls through to regex

    try:
        statements = sqlglot.parse(sql)
    except Exception as exc:
        return f"SQL parse error: {exc}"

    if not statements:
        return "SQL query cannot be empty."

    for stmt in statements:
        if stmt is None:
            continue
        if not isinstance(stmt, (exp.Select, exp.With)):
            return (
                f"Only SELECT queries are allowed. "
                f"Found: {type(stmt).__name__}. "
                "INSERT, UPDATE, DELETE, DROP, and other write operations are not permitted."
            )
        if isinstance(stmt, exp.With) and stmt.find(exp.Select) is None:
            return "WITH clause must end with a SELECT statement."

    return None


def validate_sql(sql: str) -> None:
    """Raise ValueError if SQL is not a safe SELECT/WITH query."""
    if not sql or not sql.strip():
        raise ValueError("SQL query cannot be empty.")

    # Try sqlglot AST validation first (catches semicolon-chained statements)
    err = _sqlglot_validate(sql)
    if err is not None:
        raise ValueError(err)

    # Regex fallback when sqlglot is not installed
    clean = _strip_comments(sql)
    if not clean:
        raise ValueError("SQL query cannot be empty after stripping comments.")
    if not _ALLOWED_START_RE.match(clean):
        raise ValueError(
            "Only SELECT (or WITH … SELECT) queries are allowed. "
            "INSERT, UPDATE, DELETE, DROP, and other write operations are not permitted."
        )
    if _FORBIDDEN_RE.search(clean):
        raise ValueError(
            "Query contains a forbidden SQL keyword. Only read-only SELECT queries are supported."
        )

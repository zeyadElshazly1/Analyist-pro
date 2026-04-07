from __future__ import annotations

import datetime
import logging
import re
import time

import pandas as pd

logger = logging.getLogger(__name__)

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|COPY|PRAGMA|EXECUTE|TRUNCATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)
_ALLOWED_START = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
_COMMENT_SINGLE = re.compile(r"--[^\n]*")
_COMMENT_MULTI = re.compile(r"/\*.*?\*/", re.DOTALL)

MAX_ROWS = 500
# Hard wall on query execution time to prevent runaway cross-joins
QUERY_TIMEOUT_SECONDS = 30


def _strip_comments(sql: str) -> str:
    sql = _COMMENT_SINGLE.sub("", sql)
    sql = _COMMENT_MULTI.sub("", sql)
    return sql.strip()


def validate_sql(sql: str) -> None:
    """Raise ValueError if SQL is not a safe SELECT/WITH query."""
    if not sql or not sql.strip():
        raise ValueError("SQL query cannot be empty.")
    clean = _strip_comments(sql)
    if not clean:
        raise ValueError("SQL query cannot be empty after stripping comments.")
    if not _ALLOWED_START.match(clean):
        raise ValueError(
            "Only SELECT (or WITH … SELECT) queries are allowed. "
            "INSERT, UPDATE, DELETE, DROP, and other write operations are not permitted."
        )
    if _FORBIDDEN.search(clean):
        raise ValueError(
            "Query contains a forbidden SQL keyword (INSERT/UPDATE/DELETE/DROP etc.). "
            "Only read-only SELECT queries are supported."
        )


def execute_query(df: pd.DataFrame, sql: str) -> dict:
    validate_sql(sql)

    try:
        import duckdb  # noqa: PLC0415
    except ImportError:
        raise ImportError(
            "DuckDB is not installed. Add 'duckdb>=0.10.0' to requirements.txt."
        )

    conn = duckdb.connect(database=":memory:")
    try:
        conn.register("data", df)

        # Apply a timeout via DuckDB's built-in thread-safe cancellation
        conn.execute(f"SET threads TO 2")
        conn.execute(f"SET memory_limit = '512MB'")

        t0 = time.monotonic()
        rel = conn.execute(sql)

        elapsed = time.monotonic() - t0
        if elapsed > QUERY_TIMEOUT_SECONDS:
            raise TimeoutError(
                f"Query exceeded the {QUERY_TIMEOUT_SECONDS}s time limit "
                f"(took {elapsed:.1f}s). Simplify your query."
            )

        rows_raw = rel.fetchall()
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        # Guard against queries that return no column description (e.g. EXPLAIN)
        if rel.description is None:
            raise ValueError("Query returned no column metadata. Only SELECT queries that return rows are supported.")

        columns = [desc[0] for desc in rel.description]

        truncated = len(rows_raw) > MAX_ROWS
        rows_raw = rows_raw[:MAX_ROWS]

        rows = [dict(zip(columns, row)) for row in rows_raw]
        # Serialize non-JSON-native types
        for row in rows:
            for k, v in row.items():
                if v is None:
                    pass
                elif hasattr(v, "item"):  # numpy scalar
                    row[k] = v.item()
                elif isinstance(v, (datetime.datetime, datetime.date)):
                    row[k] = v.isoformat()
                elif isinstance(v, float) and v != v:  # float NaN
                    row[k] = None
                elif isinstance(v, bytes):
                    row[k] = v.decode("utf-8", errors="replace")

        if elapsed_ms > 5000:
            logger.warning(f"Slow SQL query ({elapsed_ms}ms): {sql[:200]}")

        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_time_ms": elapsed_ms,
            "sql": sql,
            "truncated": truncated,
        }
    except (ValueError, TimeoutError):
        raise
    except Exception as e:
        logger.error(f"SQL execution error: {type(e).__name__}: {e} | SQL: {sql[:300]}")
        raise ValueError(f"Query failed: {e}") from e
    finally:
        conn.close()


def get_schema(df: pd.DataFrame) -> list[dict]:
    schema = []
    for col in df.columns:
        sample = df[col].dropna().unique()[:3].tolist()
        sample = [str(v) for v in sample]
        schema.append({
            "name": col,
            "dtype": str(df[col].dtype),
            "sample_values": sample,
        })
    return schema

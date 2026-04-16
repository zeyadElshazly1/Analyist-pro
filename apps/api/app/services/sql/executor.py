"""
SQL query executor.

execute_query(df, sql) → dict

Features:
  - Validates SQL with the AST-based validator before execution
  - Auto-injects LIMIT when not present (prevents unbounded result sets)
  - True threaded timeout: conn.interrupt() cancels an in-flight DuckDB query
  - Translates raw DuckDB errors into human-readable messages
"""
from __future__ import annotations

import datetime
import logging
import re
import threading
import time

import pandas as pd

from .constants import MAX_ROWS, QUERY_TIMEOUT_SECONDS
from .error_translator import translate_error
from .validator import validate_sql

logger = logging.getLogger(__name__)


def _inject_limit(sql: str, max_rows: int) -> str:
    """Append LIMIT clause if none is present."""
    try:
        import sqlglot                          # noqa: PLC0415
        from sqlglot import expressions as exp  # noqa: PLC0415
        parsed = sqlglot.parse_one(sql)
        if parsed is not None and parsed.find(exp.Limit) is not None:
            return sql
    except Exception:
        if re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
            return sql
    return sql.rstrip().rstrip(";") + f" LIMIT {max_rows}"


def _run_with_timeout(conn, sql: str, timeout: float):
    """Execute *sql* on *conn* in a daemon thread; interrupt on timeout."""
    result_holder: list = [None]
    error_holder:  list = [None]

    def _worker() -> None:
        try:
            result_holder[0] = conn.execute(sql)
        except Exception as exc:  # noqa: BLE001
            error_holder[0] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        conn.interrupt()
        thread.join(timeout=2.0)
        raise TimeoutError(
            f"Query exceeded the {timeout}s time limit. Simplify your query."
        )

    if error_holder[0] is not None:
        raise error_holder[0]
    return result_holder[0]


def execute_query(df: pd.DataFrame, sql: str) -> dict:
    validate_sql(sql)

    try:
        import duckdb  # noqa: PLC0415
    except ImportError:
        raise ImportError("DuckDB is not installed. Add 'duckdb>=0.10.0' to requirements.txt.")

    sql_with_limit = _inject_limit(sql, MAX_ROWS + 1)

    conn = duckdb.connect(database=":memory:")
    try:
        conn.register("data", df)
        conn.execute("SET threads TO 2")
        conn.execute("SET memory_limit = '512MB'")

        t0 = time.monotonic()
        rel = _run_with_timeout(conn, sql_with_limit, QUERY_TIMEOUT_SECONDS)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if rel.description is None:
            raise ValueError(
                "Query returned no column metadata. "
                "Only SELECT queries that return rows are supported."
            )

        columns = [desc[0] for desc in rel.description]
        rows_raw = rel.fetchall()

        truncated = len(rows_raw) > MAX_ROWS
        rows_raw  = rows_raw[:MAX_ROWS]

        rows: list[dict] = [dict(zip(columns, row)) for row in rows_raw]
        for row in rows:
            for k, v in row.items():
                if v is None:
                    pass
                elif hasattr(v, "item"):
                    row[k] = v.item()
                elif isinstance(v, (datetime.datetime, datetime.date)):
                    row[k] = v.isoformat()
                elif isinstance(v, float) and v != v:
                    row[k] = None
                elif isinstance(v, bytes):
                    row[k] = v.decode("utf-8", errors="replace")

        if elapsed_ms > 5000:
            logger.warning("Slow SQL query (%dms): %s", elapsed_ms, sql[:200])

        return {
            "columns":          columns,
            "rows":             rows,
            "row_count":        len(rows),
            "execution_time_ms": elapsed_ms,
            "sql":              sql,
            "truncated":        truncated,
        }

    except (ValueError, TimeoutError):
        raise
    except Exception as exc:
        logger.error(
            "SQL execution error: %s: %s | SQL: %s",
            type(exc).__name__, exc, sql[:300],
        )
        raise ValueError(translate_error(exc, df.columns.tolist())) from exc
    finally:
        conn.close()

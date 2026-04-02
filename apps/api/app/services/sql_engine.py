from __future__ import annotations

import datetime
import re
import time

import pandas as pd

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|COPY|PRAGMA|EXECUTE|TRUNCATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)
_ALLOWED_START = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
_COMMENT_SINGLE = re.compile(r"--[^\n]*")
_COMMENT_MULTI = re.compile(r"/\*.*?\*/", re.DOTALL)

MAX_ROWS = 500


def _strip_comments(sql: str) -> str:
    sql = _COMMENT_SINGLE.sub("", sql)
    sql = _COMMENT_MULTI.sub("", sql)
    return sql.strip()


def validate_sql(sql: str) -> None:
    """Raise ValueError if SQL is not a safe SELECT/WITH query."""
    clean = _strip_comments(sql)
    if not _ALLOWED_START.match(clean):
        raise ValueError("Only SELECT (or WITH ... SELECT) queries are allowed.")
    if _FORBIDDEN.search(clean):
        raise ValueError("Query contains forbidden SQL statements (INSERT/UPDATE/DELETE/DROP etc).")


def execute_query(df: pd.DataFrame, sql: str) -> dict:
    validate_sql(sql)

    try:
        import duckdb
    except ImportError:
        raise ImportError(
            "DuckDB is not installed. Add 'duckdb>=0.10.0' to requirements.txt."
        )

    conn = duckdb.connect(database=":memory:")
    try:
        conn.register("data", df)
        t0 = time.monotonic()
        rel = conn.execute(sql)
        rows_raw = rel.fetchall()
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        columns = [desc[0] for desc in rel.description]

        truncated = len(rows_raw) > MAX_ROWS
        rows_raw = rows_raw[:MAX_ROWS]

        rows = [dict(zip(columns, row)) for row in rows_raw]
        # convert non-serializable types
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

        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_time_ms": elapsed_ms,
            "sql": sql,
            "truncated": truncated,
        }
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"SQL execution error: {e}") from e
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

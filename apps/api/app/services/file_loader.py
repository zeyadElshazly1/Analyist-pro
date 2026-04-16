"""
Dataset loader with smart messy-file ingestion.

Public API (unchanged for all 16 existing callers):
    load_dataset(file_path) → pd.DataFrame

New opt-in API (for callers wanting parse diagnostics):
    load_dataset_with_report(file_path) → (pd.DataFrame, ParseReport)

The ingestion pipeline runs before pandas:
  sniff_csv() → detect structure, header row, preamble, footer
  pd.read_csv() with inferred skiprows / delimiter
  normalize_schema() → strip junk columns, dedup names, remove repeated headers

If the pipeline fails for any reason the original simple loader is used as
fallback — existing behaviour is never regressed.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_ENCODING_FALLBACKS = ["utf-8-sig", "utf-8", "latin-1", "cp1252", "iso-8859-1"]


# ── Public API ────────────────────────────────────────────────────────────────

def load_dataset(file_path: str) -> pd.DataFrame:
    """
    Load a CSV or Excel file into a DataFrame.

    Unchanged return type — all existing callers work without modification.
    The smart ingestion pipeline runs transparently; any failure falls back
    to the original simple loader.
    """
    df, _ = load_dataset_with_report(file_path)
    return df


def load_dataset_with_report(file_path: str):
    """
    Load a file and return (DataFrame, ParseReport).

    ParseReport carries: file_kind, confidence, warnings, metadata (title /
    source extracted from preamble), table_start_row, header_row,
    footer_start_row, status.
    """
    from .ingestion import ParseReport

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    if suffix in {".xlsx", ".xls"}:
        return _smart_load_excel(path)

    if suffix == ".csv":
        return _smart_load_csv(path)

    raise ValueError(f"Unsupported file type: '{suffix}'. Upload a CSV or Excel file.")


# ── CSV ───────────────────────────────────────────────────────────────────────

def _smart_load_csv(path: Path):
    from .ingestion import (
        ParseReport,
        extract_preamble_metadata,
        normalize_schema,
        sniff_csv,
    )

    report = ParseReport()

    try:
        sniff = sniff_csv(path)
        report.file_kind        = sniff.file_kind
        report.confidence       = sniff.confidence
        report.table_start_row  = sniff.table_start_row
        report.header_row       = sniff.header_row
        report.footer_start_row = sniff.footer_start_row

        raw_bytes = path.read_bytes()
        encoding  = _detect_encoding(raw_bytes)

        # Build skiprows: all raw lines before the header row
        header_row = sniff.header_row
        skiprows   = list(range(header_row)) if header_row > 0 else None

        if skiprows:
            report.warnings.append(f"Skipped {len(skiprows)} preamble row(s)")
            report.metadata_rows = list(range(header_row))
            try:
                raw_lines   = path.read_text(encoding=encoding, errors="replace").splitlines()
                report.metadata = extract_preamble_metadata(raw_lines, header_row)
            except Exception:
                pass

        try:
            df = pd.read_csv(
                path,
                encoding=encoding,
                on_bad_lines="skip",
                skiprows=skiprows,
                sep=sniff.delimiter,
            )
        except Exception:
            # Encoding retry loop
            df = _load_csv_fallback(path)
            report.warnings.append("Encoding retry used during CSV load")

        # Trim footer rows
        footer = sniff.footer_start_row
        if footer is not None:
            data_rows = footer - header_row - 1   # rows of actual data before footer
            if 0 < data_rows < len(df):
                df = df.iloc[:data_rows]
                report.warnings.append(
                    f"Trimmed footer rows starting at raw line {footer}"
                )

        df = normalize_schema(df, report)
        report.status = "parsed_with_warnings" if report.warnings else "ok"
        report.parsing_decisions.append(
            f"file_kind={sniff.file_kind} header_row={header_row} "
            f"delimiter={repr(sniff.delimiter)} confidence={sniff.confidence}"
        )

        logger.info(
            "Loaded CSV %s via ingestion pipeline: %d rows × %d cols "
            "[%s, confidence=%.2f]",
            path.name, len(df), len(df.columns), sniff.file_kind, sniff.confidence,
        )
        return df, report

    except Exception as exc:
        report.status     = "fallback"
        report.confidence = 0.5
        report.warnings.append(f"Smart parse failed ({exc}) — using basic loader")
        logger.debug("Smart CSV parse failed for %s: %s", path.name, exc)
        df = _load_csv_fallback(path)
        return df, report


def _load_csv_fallback(path: Path) -> pd.DataFrame:
    """Original Polars → pandas encoding-trial loader."""
    df = _load_csv_polars(path)
    if df is not None:
        return df

    raw = path.read_bytes()
    encoding = _detect_encoding(raw)
    encodings_to_try = [encoding] + [e for e in _ENCODING_FALLBACKS if e != encoding]

    for enc in encodings_to_try:
        try:
            df = pd.read_csv(path, encoding=enc, on_bad_lines="skip")
            n_original = raw.count(b"\n")
            n_loaded   = len(df)
            if n_original > n_loaded + 1:
                logger.warning(
                    "CSV %s: skipped %d malformed row(s) (encoding=%s)",
                    path.name, n_original - n_loaded - 1, enc,
                )
            return df
        except (UnicodeDecodeError, LookupError):
            continue
        except Exception as e:
            raise ValueError(f"Failed to read CSV file: {e}") from e

    raise ValueError(
        f"Could not decode '{path.name}' with any of: {encodings_to_try}. "
        "Please save the file as UTF-8 and re-upload."
    )


# ── Excel ─────────────────────────────────────────────────────────────────────

def _smart_load_excel(path: Path):
    from .ingestion import ParseReport, find_data_region, normalize_schema

    report = ParseReport(file_kind="excel")

    try:
        region   = find_data_region(path)
        skiprows = region.get("skiprows")

        if skiprows:
            report.warnings.append(f"Skipped {skiprows} decorative row(s) in Excel sheet")
            report.header_row       = skiprows
            report.table_start_row  = skiprows

        df = pd.read_excel(path, skiprows=skiprows)
        df = normalize_schema(df, report)

        report.confidence = 0.92 if skiprows else 0.97
        report.status     = "parsed_with_warnings" if report.warnings else "ok"

        logger.info(
            "Loaded Excel %s: %d rows × %d cols (skiprows=%s)",
            path.name, len(df), len(df.columns), skiprows,
        )
        return df, report

    except Exception as exc:
        report.status     = "fallback"
        report.confidence = 0.5
        report.warnings.append(f"Smart Excel parse failed ({exc}) — using basic loader")
        try:
            df = pd.read_excel(path)
        except Exception as e:
            raise ValueError(f"Failed to read Excel file: {e}") from e
        return df, report


# ── Encoding helpers (unchanged from original) ────────────────────────────────

def _detect_encoding(raw: bytes) -> str:
    try:
        import chardet
        result   = chardet.detect(raw[:50_000])
        encoding = result.get("encoding") or "utf-8"
        logger.debug("chardet detected encoding=%s confidence=%.2f",
                     encoding, result.get("confidence", 0))
        return encoding
    except ImportError:
        return "utf-8-sig"


def _load_csv_polars(path: Path) -> pd.DataFrame | None:
    try:
        import polars as pl
        df_pl = pl.read_csv(
            path,
            infer_schema_length=10_000,
            ignore_errors=True,
            truncate_ragged_lines=True,
            encoding="utf8-lossy",
        )
        df = df_pl.to_pandas()
        logger.info("Loaded CSV via Polars %s: %d rows × %d cols", path.name, len(df), len(df.columns))
        return df
    except ImportError:
        return None
    except Exception as e:
        logger.debug("Polars CSV load failed for %s: %s — falling back to pandas", path.name, e)
        return None

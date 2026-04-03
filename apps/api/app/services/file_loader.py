import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Encoding candidates tried in order when chardet is unavailable
_ENCODING_FALLBACKS = ["utf-8-sig", "utf-8", "latin-1", "cp1252", "iso-8859-1"]


def _detect_encoding(raw: bytes) -> str:
    """
    Detect the most likely encoding for raw bytes.
    Uses chardet if installed, falls back to a heuristic trial list.
    """
    try:
        import chardet
        result = chardet.detect(raw[:50_000])  # Sample first 50KB for speed
        encoding = result.get("encoding") or "utf-8"
        confidence = result.get("confidence", 0)
        logger.debug(f"chardet detected encoding={encoding} confidence={confidence:.2f}")
        return encoding
    except ImportError:
        return "utf-8-sig"  # Best general-purpose default


def load_dataset(file_path: str) -> pd.DataFrame:
    """
    Load a CSV or Excel file into a DataFrame.

    - Auto-detects encoding (chardet if available, otherwise trial fallback)
    - Reports how many rows were skipped on bad lines
    - Raises FileNotFoundError, ValueError on invalid inputs
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    # ── Excel ─────────────────────────────────────────────────────────────────
    if suffix in {".xlsx", ".xls"}:
        try:
            df = pd.read_excel(path)
            logger.info(f"Loaded Excel {path.name}: {len(df)} rows × {len(df.columns)} cols")
            return df
        except Exception as e:
            raise ValueError(f"Failed to read Excel file: {e}") from e

    # ── CSV ───────────────────────────────────────────────────────────────────
    if suffix == ".csv":
        raw = path.read_bytes()
        encoding = _detect_encoding(raw)

        # Try detected encoding first, then fall back through candidates
        encodings_to_try = [encoding] + [e for e in _ENCODING_FALLBACKS if e != encoding]

        for enc in encodings_to_try:
            try:
                df = pd.read_csv(path, encoding=enc, on_bad_lines="skip")
                n_original = _count_raw_rows(raw)
                n_loaded = len(df)
                if n_original > n_loaded + 1:  # +1 for header row
                    skipped = n_original - n_loaded - 1
                    logger.warning(
                        f"CSV {path.name}: skipped {skipped} malformed row(s) "
                        f"(encoding={enc})"
                    )
                else:
                    logger.info(
                        f"Loaded CSV {path.name}: {n_loaded} rows × {len(df.columns)} cols "
                        f"(encoding={enc})"
                    )
                return df
            except (UnicodeDecodeError, LookupError):
                logger.debug(f"Encoding {enc} failed for {path.name}, trying next")
                continue
            except Exception as e:
                raise ValueError(f"Failed to read CSV file: {e}") from e

        raise ValueError(
            f"Could not decode '{path.name}' with any of: {encodings_to_try}. "
            "Please save the file as UTF-8 and re-upload."
        )

    raise ValueError(f"Unsupported file type: '{suffix}'. Upload a CSV or Excel file.")


def _count_raw_rows(raw: bytes) -> int:
    """Quick line count without full parse — used only for skipped-rows warning."""
    try:
        return raw.count(b"\n")
    except Exception:
        return 0

"""
Shared dataset loading utility.

load_prepared(project_id) → pd.DataFrame

Single entry point for all routes that need a cleaned DataFrame.
Resolution order:
  1. In-memory PROJECT_FILES cache (fastest)
  2. Persistent PreparedDataset record → load Parquet (survives restarts)
  3. Load raw file from disk, clean, serialize to Parquet, write DB record

Raises HTTPException on any failure.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pandas as pd
from fastapi import HTTPException

from app.config import UPLOAD_DIR
from app.services.cleaner import clean_dataset
from app.services.file_loader import load_dataset
from app.state import get_project_file_info

logger = logging.getLogger(__name__)

PREPARED_DIR = os.path.join(UPLOAD_DIR, "prepared")
os.makedirs(PREPARED_DIR, exist_ok=True)


def _parquet_path(project_id: int, file_hash: str) -> str:
    return os.path.join(PREPARED_DIR, f"project_{project_id}_{file_hash[:16]}.parquet")


def _load_from_parquet(path: str) -> pd.DataFrame | None:
    try:
        if Path(path).exists():
            return pd.read_parquet(path)
    except Exception as e:
        logger.debug(f"Parquet load failed for {path}: {e}")
    return None


def _save_to_parquet(df: pd.DataFrame, path: str) -> bool:
    try:
        df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")
        return True
    except Exception as e:
        logger.debug(f"Parquet save failed for {path}: {e}")
        return False


def _persist_prepared(
    project_id: int,
    file_hash: str,
    parquet_path: str,
    df: pd.DataFrame,
    cleaning_meta: dict,
) -> None:
    """Write a PreparedDataset record to the DB (best-effort, never raises)."""
    try:
        from app.db import SessionLocal
        from app.models import PreparedDataset

        db = SessionLocal()
        try:
            existing = (
                db.query(PreparedDataset)
                .filter(
                    PreparedDataset.project_id == project_id,
                    PreparedDataset.file_hash == file_hash,
                )
                .first()
            )
            if not existing:
                record = PreparedDataset(
                    project_id=project_id,
                    file_hash=file_hash,
                    stored_path=parquet_path,
                    rows=len(df),
                    columns=len(df.columns),
                    cleaning_meta_json=json.dumps(cleaning_meta, default=str),
                )
                db.add(record)
                db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"PreparedDataset DB write failed for project {project_id}: {e}")


def _find_prepared_in_db(project_id: int, file_hash: str) -> str | None:
    """Return the parquet path from DB if it exists and file is present."""
    try:
        from app.db import SessionLocal
        from app.models import PreparedDataset

        db = SessionLocal()
        try:
            record = (
                db.query(PreparedDataset)
                .filter(
                    PreparedDataset.project_id == project_id,
                    PreparedDataset.file_hash == file_hash,
                )
                .first()
            )
            if record and Path(record.stored_path).exists():
                return record.stored_path
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"PreparedDataset DB lookup failed for project {project_id}: {e}")
    return None


def load_prepared(project_id: int) -> pd.DataFrame:
    info = get_project_file_info(project_id)
    if not info:
        raise HTTPException(status_code=404, detail="No uploaded file for this project.")

    path = info["path"]
    file_hash = info.get("file_hash") or ""

    # 1. Try DB-registered Parquet artifact
    if file_hash:
        parquet_path = _parquet_path(project_id, file_hash)
        df = _load_from_parquet(parquet_path)
        if df is not None:
            return df

        # Check DB for a different path (e.g. if PREPARED_DIR moved)
        db_path = _find_prepared_in_db(project_id, file_hash)
        if db_path:
            df = _load_from_parquet(db_path)
            if df is not None:
                return df

    # 2. Load raw file and clean
    try:
        df_raw = load_dataset(path)
        df_clean, cleaning_report, cleaning_summary = clean_dataset(df_raw)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file not found on disk.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")

    # 3. Persist for reuse (best-effort)
    if file_hash:
        parquet_path = _parquet_path(project_id, file_hash)
        saved = _save_to_parquet(df_clean, parquet_path)
        if saved:
            cleaning_meta = (
                cleaning_summary if isinstance(cleaning_summary, dict)
                else {"note": str(cleaning_summary)}
            )
            _persist_prepared(project_id, file_hash, parquet_path, df_clean, cleaning_meta)

    return df_clean

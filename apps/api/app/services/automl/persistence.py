"""
Model artifact persistence.

_MODELS_DIR            — directory where joblib artifacts are stored
save_model_artifacts   — serialise artifacts dict to disk
load_model_artifacts   — deserialise artifacts dict from disk
"""
from __future__ import annotations

import logging
import os

import joblib

logger = logging.getLogger(__name__)

_MODELS_DIR = os.getenv("MODELS_DIR", "models")
os.makedirs(_MODELS_DIR, exist_ok=True)


def _model_path(project_id: int) -> str:
    return os.path.join(_MODELS_DIR, f"project_{project_id}.joblib")


def save_model_artifacts(project_id: int, artifacts: dict) -> None:
    joblib.dump(artifacts, _model_path(project_id))


def load_model_artifacts(project_id: int) -> dict | None:
    path = _model_path(project_id)
    if not os.path.exists(path):
        return None
    try:
        return joblib.load(path)
    except Exception as exc:
        logger.warning("Failed to load model for project %s: %s", project_id, exc)
        return None

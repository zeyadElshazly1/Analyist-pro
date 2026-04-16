"""
Backward-compatibility shim for app.services.automl_service.

All production callers do:
    from app.services.automl_service import train_models, score_rows, ...

All logic lives in app.services.automl.
Do not add logic to this file.
"""
from app.services.automl import (  # noqa: F401
    _MODELS_DIR,
    detect_problem_type,
    load_model_artifacts,
    save_model_artifacts,
    score_rows,
    train_models,
)

__all__ = [
    "_MODELS_DIR",
    "detect_problem_type",
    "load_model_artifacts",
    "save_model_artifacts",
    "score_rows",
    "train_models",
]

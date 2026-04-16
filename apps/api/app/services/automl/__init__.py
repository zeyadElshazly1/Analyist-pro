"""
Analyst Pro AutoML package.

Re-exports the public API used by app.services.automl_service and
app.routes.ml.  Also re-exports _MODELS_DIR so that conftest.py can
monkeypatch it via app.services.automl.persistence._MODELS_DIR.
"""
from .persistence import (       # noqa: F401
    _MODELS_DIR,
    save_model_artifacts,
    load_model_artifacts,
)
from .problem_detector import detect_problem_type  # noqa: F401
from .scorer import score_rows                     # noqa: F401
from .trainer import train_models                  # noqa: F401

__all__ = [
    "_MODELS_DIR",
    "detect_problem_type",
    "load_model_artifacts",
    "save_model_artifacts",
    "score_rows",
    "train_models",
]

"""
Model registry.

get_models(problem_type) → dict[str, estimator]

Returns a fresh dict of unfitted sklearn-compatible estimators for the given
problem type.  XGBoost and LightGBM are included when available.
"""
from __future__ import annotations

import logging

from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import (
    LinearRegression,
    LogisticRegression,
    Ridge,
    RidgeClassifier,
)

logger = logging.getLogger(__name__)


def get_models(problem_type: str) -> dict:
    """Return a name→estimator dict for the given problem type."""
    if problem_type == "regression":
        models: dict = {
            "Linear Regression": LinearRegression(),
            "Ridge":             Ridge(),
            "Random Forest":     RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1),
            "Gradient Boosting": GradientBoostingRegressor(
                n_estimators=100, random_state=42,
                n_iter_no_change=10, validation_fraction=0.1,
            ),
        }
    else:
        models = {
            "Logistic Regression": LogisticRegression(max_iter=500, random_state=42),
            "Ridge Classifier":    RidgeClassifier(),
            "Random Forest":       RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1),
            "Gradient Boosting":   GradientBoostingClassifier(
                n_estimators=100, random_state=42,
                n_iter_no_change=10, validation_fraction=0.1,
            ),
        }

    # Optional: XGBoost
    try:
        import xgboost as xgb
        if problem_type == "regression":
            models["XGBoost"] = xgb.XGBRegressor(
                n_estimators=100, random_state=42, verbosity=0, n_jobs=-1
            )
        else:
            models["XGBoost"] = xgb.XGBClassifier(
                n_estimators=100, random_state=42, verbosity=0, n_jobs=-1
            )
    except ImportError:
        pass

    # Optional: LightGBM
    try:
        import lightgbm as lgb
        if problem_type == "regression":
            models["LightGBM"] = lgb.LGBMRegressor(
                n_estimators=100, random_state=42, verbosity=-1
            )
        else:
            models["LightGBM"] = lgb.LGBMClassifier(
                n_estimators=100, random_state=42, verbosity=-1
            )
    except ImportError:
        pass

    return models

"""
AutoML training orchestrator.

train_models(df, target_col) → dict

End-to-end pipeline:
  1. Drop rows with missing target; drop cols with >70% missing; drop ID-like cols
  2. Detect problem type (classification vs regression)
  3. Encode target (LabelEncoder for classification)
  4. Build ColumnTransformer preprocessor (OHE for categoricals, median+scale for numerics)
  5. Train all models from the zoo in parallel, each wrapped in a full sklearn Pipeline
     so CV folds never see test-fold preprocessing statistics
  6. Stratified train/test split for classification
  7. Compute permutation feature importance on the best model
  8. Return JSON-serialisable result + _artifacts dict for persistence
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline as SKPipeline
from sklearn.preprocessing import LabelEncoder

from .model_zoo import get_models
from .preprocessor import build_preprocessor
from .problem_detector import detect_problem_type

logger = logging.getLogger(__name__)


def train_models(df: pd.DataFrame, target_col: str) -> dict:  # noqa: C901
    notes: list[str] = []
    df = df.copy()

    # ── Drop rows where target is missing ────────────────────────────────────
    df = df.dropna(subset=[target_col])
    if len(df) < 10:
        raise ValueError("Need at least 10 non-null rows in the target column to train.")

    # ── Drop cols with >70% missing ───────────────────────────────────────────
    thresh = 0.7 * len(df)
    df = df.loc[:, df.isnull().sum() <= thresh]

    # ── Drop ID-like cols (all unique, object dtype) ──────────────────────────
    id_cols = [
        c for c in df.columns
        if c != target_col
        and df[c].nunique() == len(df)
        and df[c].dtype == object
    ]
    if id_cols:
        df = df.drop(columns=id_cols)
        notes.append(f"Dropped {len(id_cols)} ID-like column(s): {id_cols}")

    problem_type = detect_problem_type(df, target_col)

    y_raw = df[target_col].copy()
    X_raw = df.drop(columns=[target_col])

    # ── Drop datetime columns (can't use raw timestamps) ─────────────────────
    dt_cols = X_raw.select_dtypes(include=["datetime64"]).columns.tolist()
    if dt_cols:
        X_raw = X_raw.drop(columns=dt_cols)
        notes.append(f"Dropped {len(dt_cols)} datetime column(s)")

    # ── Encode target ─────────────────────────────────────────────────────────
    le_target = None
    class_labels = None
    if problem_type == "classification":
        le_target = LabelEncoder()
        y = le_target.fit_transform(y_raw.astype(str))
        class_labels = list(le_target.classes_)
        if len(np.unique(y)) < 2:
            raise ValueError("Target column has only one class — cannot train a classifier.")
    else:
        try:
            y = y_raw.values.astype(float)
        except (ValueError, TypeError):
            problem_type = "classification"
            le_target = LabelEncoder()
            y = le_target.fit_transform(y_raw.astype(str))
            class_labels = list(le_target.classes_)
            notes.append("Target could not be cast to float — switched to classification.")

    # ── Identify feature types ────────────────────────────────────────────────
    numeric_features     = X_raw.select_dtypes(include=[np.number]).columns.tolist()
    categorical_features = X_raw.select_dtypes(include=["object", "category"]).columns.tolist()
    feature_names        = numeric_features + categorical_features  # stable order
    X_raw                = X_raw[feature_names]                    # reorder to match

    if categorical_features:
        notes.append(f"OneHot-encoded {len(categorical_features)} categorical column(s)")

    missing_total = X_raw.isnull().sum().sum()
    if missing_total > 0:
        notes.append(f"Imputed {int(missing_total)} missing value(s) with median (numeric) / constant (categorical)")

    # ── Preprocessor (ColumnTransformer) ──────────────────────────────────────
    preprocessor = build_preprocessor(numeric_features, categorical_features)

    # ── Stratified train/test split ───────────────────────────────────────────
    split_kwargs: dict = {}
    if problem_type == "classification":
        split_kwargs["stratify"] = y
    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X_raw, y, test_size=0.2, random_state=42, **split_kwargs
    )

    # ── Model definitions ─────────────────────────────────────────────────────
    base_models = get_models(problem_type)
    scoring     = "r2" if problem_type == "regression" else "f1_weighted"

    # ── Parallel train & evaluate (each model in a full Pipeline) ────────────
    def _train_one(name: str, model) -> tuple[str, object, dict, float]:
        try:
            pipe = SKPipeline([("preprocessor", preprocessor), ("model", model)])
            cv_scores = cross_val_score(pipe, X_train_raw, y_train, cv=5, scoring=scoring, n_jobs=-1)
            pipe.fit(X_train_raw, y_train)
            preds = pipe.predict(X_test_raw)

            if problem_type == "regression":
                rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
                r2   = float(r2_score(y_test, preds))
                mae  = float(mean_absolute_error(y_test, preds))
                result = {
                    "name":     name,
                    "rmse":     round(rmse, 4),
                    "r2":       round(r2, 4),
                    "mae":      round(mae, 4),
                    "cv_score": round(float(cv_scores.mean()), 4),
                    "cv_std":   round(float(cv_scores.std()), 4),
                }
                score = r2
            else:
                acc = float(accuracy_score(y_test, preds))
                f1  = float(f1_score(y_test, preds, average="weighted"))
                auc = None
                try:
                    if hasattr(pipe, "predict_proba"):
                        proba = pipe.predict_proba(X_test_raw)
                        if len(np.unique(y)) == 2:
                            auc = float(roc_auc_score(y_test, proba[:, 1]))
                        else:
                            auc = float(roc_auc_score(y_test, proba, multi_class="ovr"))
                except Exception:
                    pass
                result = {
                    "name":     name,
                    "accuracy": round(acc, 4),
                    "f1":       round(f1, 4),
                    "auc":      round(auc, 4) if auc is not None else None,
                    "cv_score": round(float(cv_scores.mean()), 4),
                    "cv_std":   round(float(cv_scores.std()), 4),
                }
                score = f1

            return name, pipe, result, score

        except Exception as exc:
            return name, None, {"name": name, "error": str(exc)}, -np.inf

    parallel_results = Parallel(n_jobs=4, prefer="threads")(
        delayed(_train_one)(name, model) for name, model in base_models.items()
    )

    results: list[dict] = []
    best_score    = -np.inf
    best_name     = ""
    best_pipeline = None

    for name, fitted_pipe, result, score in parallel_results:
        results.append(result)
        if score > best_score:
            best_score    = score
            best_name     = name
            best_pipeline = fitted_pipe

    results.sort(key=lambda x: x.get("cv_score", -999), reverse=True)

    # ── Permutation feature importance (on raw DataFrame → full pipeline) ─────
    feature_importance: list[dict] = []
    if best_pipeline is not None and feature_names:
        try:
            perm = permutation_importance(
                best_pipeline, X_test_raw, y_test, n_repeats=5, random_state=42
            )
            imp = perm.importances_mean
            feature_importance = sorted(
                [
                    {"feature": feature_names[i], "importance": round(float(imp[i]), 4)}
                    for i in range(len(feature_names))
                ],
                key=lambda x: abs(x["importance"]),
                reverse=True,
            )[:15]
        except Exception:
            try:
                raw_imp = best_pipeline.named_steps["model"].feature_importances_
                feature_importance = sorted(
                    [
                        {"feature": feature_names[i], "importance": round(float(raw_imp[i]), 4)}
                        for i in range(min(len(feature_names), len(raw_imp)))
                    ],
                    key=lambda x: x["importance"],
                    reverse=True,
                )[:15]
            except Exception:
                pass

    # ── Predictions sample (up to 20 test rows) ───────────────────────────────
    preds_all: list[dict] = []
    if best_pipeline is not None:
        try:
            sample_X = X_test_raw.iloc[:20]
            raw_preds = best_pipeline.predict(sample_X)
            for i in range(len(raw_preds)):
                actual_val = y_test[i]
                pred_val   = raw_preds[i]
                if le_target is not None:
                    actual_val = le_target.inverse_transform([int(actual_val)])[0]
                    pred_val   = le_target.inverse_transform([int(pred_val)])[0]
                preds_all.append({"actual": actual_val, "predicted": pred_val})
        except Exception:
            pass

    # ── Confusion matrix ──────────────────────────────────────────────────────
    confusion_matrix_data = None
    if problem_type == "classification" and best_pipeline is not None:
        try:
            from sklearn.metrics import confusion_matrix
            cm = confusion_matrix(y_test, best_pipeline.predict(X_test_raw))
            confusion_matrix_data = cm.tolist()
        except Exception:
            pass

    # ── Artifact dict for persistence ─────────────────────────────────────────
    _artifacts = {
        "pipeline":        best_pipeline,
        "le_target":       le_target,
        "class_labels":    class_labels,
        "problem_type":    problem_type,
        "target_col":      target_col,
        "best_model_name": best_name,
        "feature_names":   feature_names,
        "dt_cols":         dt_cols,
    }

    return {
        "problem_type":       problem_type,
        "target_col":         target_col,
        "n_rows":             len(df),
        "n_features":         len(feature_names),
        "models":             results,
        "best_model":         best_name,
        "feature_importance": feature_importance,
        "predictions_sample": preds_all,
        "preprocessing_notes": notes,
        "confusion_matrix":   confusion_matrix_data,
        "class_labels":       class_labels,
        "_artifacts":         _artifacts,
    }

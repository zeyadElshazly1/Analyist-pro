from __future__ import annotations

import logging
import os

import joblib
import numpy as np
import pandas as pd
from joblib import Parallel, delayed

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


def score_rows(artifacts: dict, rows: list[dict]) -> list[dict]:
    """Apply the saved preprocessing pipeline and score new rows."""
    feature_names: list[str] = artifacts["feature_names"]
    encoders: dict = artifacts["encoders"]
    imputer: SimpleImputer = artifacts["imputer"]
    scaler = artifacts["scaler"]
    le_target = artifacts["le_target"]
    best_model = artifacts["best_model"]
    problem_type: str = artifacts["problem_type"]
    dt_cols: list[str] = artifacts.get("dt_cols", [])

    df = pd.DataFrame(rows)

    # Drop datetime columns the model never saw
    for col in dt_cols:
        if col in df.columns:
            df = df.drop(columns=[col])

    # Encode categoricals with the training encoders
    for col, le in encoders.items():
        if col in df.columns:
            known = set(le.classes_)
            df[col] = df[col].apply(
                lambda v: le.transform([str(v)])[0] if str(v) in known else -1
            )

    # Reorder + fill missing feature columns
    df = df.reindex(columns=feature_names, fill_value=np.nan)

    X = imputer.transform(df.values.astype(float))
    X = scaler.transform(X)

    raw_preds = best_model.predict(X)

    results = []
    for i in range(len(rows)):
        pred = raw_preds[i]
        if le_target is not None:
            pred = le_target.inverse_transform([int(pred)])[0]
        entry: dict = {"prediction": pred}

        if problem_type == "classification" and hasattr(best_model, "predict_proba"):
            try:
                proba = best_model.predict_proba(X[i : i + 1])[0]
                entry["confidence"] = round(float(max(proba)), 4)
            except Exception:
                pass

        results.append(entry)

    return results
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import (
    LinearRegression,
    LogisticRegression,
    Ridge,
    RidgeClassifier,
)
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler


def detect_problem_type(df: pd.DataFrame, target_col: str) -> str:
    col = df[target_col].dropna()
    if col.dtype == object or col.nunique() <= 20:
        return "classification"
    return "regression"


def train_models(df: pd.DataFrame, target_col: str) -> dict:  # noqa: C901
    notes: list[str] = []

    # --- preprocessing ---
    df = df.copy()

    # drop rows where target is missing
    df = df.dropna(subset=[target_col])
    if len(df) < 10:
        raise ValueError("Need at least 10 non-null rows in the target column to train.")

    # drop cols with >70 % missing
    thresh = 0.7 * len(df)
    df = df.loc[:, df.isnull().sum() <= thresh]

    # drop ID-like cols (all unique, object dtype)
    id_cols = [c for c in df.columns if c != target_col and df[c].nunique() == len(df) and df[c].dtype == object]
    if id_cols:
        df = df.drop(columns=id_cols)
        notes.append(f"Dropped {len(id_cols)} ID-like column(s): {id_cols}")

    problem_type = detect_problem_type(df, target_col)

    y_raw = df[target_col].copy()
    X_raw = df.drop(columns=[target_col])

    # encode target
    le_target = None
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
            # fall back to classification if numeric coercion fails
            problem_type = "classification"
            le_target = LabelEncoder()
            y = le_target.fit_transform(y_raw.astype(str))
            class_labels = list(le_target.classes_)
            notes.append("Target could not be cast to float — switched to classification.")
        class_labels = None

    # encode categorical features
    cat_cols = X_raw.select_dtypes(include=["object", "category"]).columns.tolist()
    encoders: dict[str, LabelEncoder] = {}
    for col in cat_cols:
        le = LabelEncoder()
        X_raw[col] = le.fit_transform(X_raw[col].astype(str))
        encoders[col] = le
    if cat_cols:
        notes.append(f"Encoded {len(cat_cols)} categorical column(s)")

    # drop datetime columns (can't use raw)
    dt_cols = X_raw.select_dtypes(include=["datetime64"]).columns.tolist()
    if dt_cols:
        X_raw = X_raw.drop(columns=dt_cols)
        notes.append(f"Dropped {len(dt_cols)} datetime column(s)")

    # impute missing
    missing_before = X_raw.isnull().sum().sum()
    imputer = SimpleImputer(strategy="median")
    X_imp = imputer.fit_transform(X_raw)
    if missing_before > 0:
        notes.append(f"Imputed {int(missing_before)} missing value(s) with median")

    # scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imp)
    feature_names = list(X_raw.columns)

    # train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42
    )

    # --- model definitions ---
    if problem_type == "regression":
        models = {
            "Linear Regression": LinearRegression(),
            "Ridge": Ridge(),
            "Random Forest": RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1),
            "Gradient Boosting": GradientBoostingRegressor(
                n_estimators=100, random_state=42, n_iter_no_change=10, validation_fraction=0.1
            ),
        }
    else:
        models = {
            "Logistic Regression": LogisticRegression(max_iter=500, random_state=42),
            "Ridge Classifier": RidgeClassifier(),
            "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1),
            "Gradient Boosting": GradientBoostingClassifier(
                n_estimators=100, random_state=42, n_iter_no_change=10, validation_fraction=0.1
            ),
        }

    # try xgboost
    try:
        import xgboost as xgb  # noqa: F401
        if problem_type == "regression":
            models["XGBoost"] = xgb.XGBRegressor(n_estimators=100, random_state=42, verbosity=0, n_jobs=-1)
        else:
            models["XGBoost"] = xgb.XGBClassifier(n_estimators=100, random_state=42, verbosity=0, n_jobs=-1)
        notes.append("XGBoost included")
    except ImportError:
        pass

    # --- parallel train & evaluate ---
    def _train_one(name: str, model) -> tuple[str, object, dict, float]:
        """Train a single model and return (name, fitted_model, metrics_dict, score)."""
        try:
            if problem_type == "regression":
                cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring="r2", n_jobs=-1)
                model.fit(X_train, y_train)
                preds = model.predict(X_test)
                rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
                r2 = float(r2_score(y_test, preds))
                mae = float(mean_absolute_error(y_test, preds))
                result = {
                    "name": name,
                    "rmse": round(rmse, 4),
                    "r2": round(r2, 4),
                    "mae": round(mae, 4),
                    "cv_score": round(float(cv_scores.mean()), 4),
                    "cv_std": round(float(cv_scores.std()), 4),
                }
                score = r2
            else:
                cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring="f1_weighted", n_jobs=-1)
                model.fit(X_train, y_train)
                preds = model.predict(X_test)
                acc = float(accuracy_score(y_test, preds))
                f1 = float(f1_score(y_test, preds, average="weighted"))
                try:
                    if hasattr(model, "predict_proba"):
                        proba = model.predict_proba(X_test)
                        if len(np.unique(y)) == 2:
                            auc = float(roc_auc_score(y_test, proba[:, 1]))
                        else:
                            auc = float(roc_auc_score(y_test, proba, multi_class="ovr"))
                    else:
                        auc = None
                except Exception:
                    auc = None
                result = {
                    "name": name,
                    "accuracy": round(acc, 4),
                    "f1": round(f1, 4),
                    "auc": round(auc, 4) if auc is not None else None,
                    "cv_score": round(float(cv_scores.mean()), 4),
                    "cv_std": round(float(cv_scores.std()), 4),
                }
                score = f1
            return name, model, result, score
        except Exception as e:
            return name, None, {"name": name, "error": str(e)}, -np.inf

    parallel_results = Parallel(n_jobs=4, prefer="threads")(
        delayed(_train_one)(name, model) for name, model in models.items()
    )

    results = []
    best_score = -np.inf
    best_name = ""
    best_model = None

    for name, fitted_model, result, score in parallel_results:
        results.append(result)
        if score > best_score:
            best_score = score
            best_name = name
            best_model = fitted_model

    # sort by cv_score desc
    results.sort(key=lambda x: x.get("cv_score", -999), reverse=True)

    # --- feature importance ---
    feature_importance = []
    if best_model is not None and feature_names:
        try:
            perm = permutation_importance(best_model, X_test, y_test, n_repeats=5, random_state=42)
            imp = perm.importances_mean
            fi = sorted(
                [{"feature": feature_names[i], "importance": round(float(imp[i]), 4)} for i in range(len(feature_names))],
                key=lambda x: abs(x["importance"]),
                reverse=True,
            )
            feature_importance = fi[:15]
        except Exception:
            # fallback: built-in feature_importances_
            try:
                imp = best_model.feature_importances_
                fi = sorted(
                    [{"feature": feature_names[i], "importance": round(float(imp[i]), 4)} for i in range(len(feature_names))],
                    key=lambda x: x["importance"],
                    reverse=True,
                )
                feature_importance = fi[:15]
            except Exception:
                pass

    # --- predictions sample ---
    preds_all = []
    if best_model is not None:
        try:
            raw_preds = best_model.predict(X_test[:20])
            for i in range(len(raw_preds)):
                actual_val = y_test[i]
                pred_val = raw_preds[i]
                if le_target is not None:
                    actual_val = le_target.inverse_transform([int(actual_val)])[0]
                    pred_val = le_target.inverse_transform([int(pred_val)])[0]
                preds_all.append({"actual": actual_val, "predicted": pred_val})
        except Exception:
            pass

    # --- confusion matrix ---
    confusion_matrix_data = None
    if problem_type == "classification" and best_model is not None:
        try:
            from sklearn.metrics import confusion_matrix
            cm = confusion_matrix(y_test, best_model.predict(X_test))
            confusion_matrix_data = cm.tolist()
        except Exception:
            pass

    # Build artifact dict for persistence (returned separately so the
    # route handler can save it keyed by project_id without mixing
    # sklearn objects into the JSON-serialisable result).
    _artifacts = {
        "best_model": best_model,
        "feature_names": feature_names,
        "encoders": encoders,
        "imputer": imputer,
        "scaler": scaler,
        "le_target": le_target,
        "class_labels": class_labels,
        "problem_type": problem_type,
        "target_col": target_col,
        "best_model_name": best_name,
        "dt_cols": dt_cols,
    }

    return {
        "problem_type": problem_type,
        "target_col": target_col,
        "n_rows": len(df),
        "n_features": len(feature_names),
        "models": results,
        "best_model": best_name,
        "feature_importance": feature_importance,
        "predictions_sample": preds_all,
        "preprocessing_notes": notes,
        "confusion_matrix": confusion_matrix_data,
        "class_labels": class_labels,
        "_artifacts": _artifacts,
    }

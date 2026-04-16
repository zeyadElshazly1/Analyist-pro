"""
Row scoring with saved model artifacts.

score_rows(artifacts, rows) → list[dict]

The sklearn Pipeline stored in artifacts["pipeline"] handles all preprocessing
(imputation, scaling, OHE) internally, so this function only needs to align
the input DataFrame columns and decode the target labels.
"""
from __future__ import annotations

import pandas as pd


def score_rows(artifacts: dict, rows: list[dict]) -> list[dict]:
    """
    Apply the saved Pipeline to new rows and return predictions.

    Each output dict contains:
        prediction  — decoded label (classification) or float (regression)
        confidence  — max class probability (classification only, when available)
    """
    pipeline      = artifacts["pipeline"]
    le_target     = artifacts["le_target"]
    problem_type  = artifacts["problem_type"]
    feature_names: list[str] = artifacts["feature_names"]
    dt_cols: list[str]       = artifacts.get("dt_cols", [])

    df = pd.DataFrame(rows)

    # Drop datetime columns the pipeline was never trained on
    for col in dt_cols:
        if col in df.columns:
            df = df.drop(columns=[col])

    # Align to training feature order; unknown columns fill with NaN
    df = df.reindex(columns=feature_names)

    raw_preds = pipeline.predict(df)

    results: list[dict] = []
    for i, pred in enumerate(raw_preds):
        if le_target is not None:
            pred = le_target.inverse_transform([int(pred)])[0]
        entry: dict = {"prediction": pred}

        if problem_type == "classification":
            try:
                proba = pipeline.predict_proba(df.iloc[i : i + 1])[0]
                entry["confidence"] = round(float(max(proba)), 4)
            except Exception:
                pass

        results.append(entry)

    return results

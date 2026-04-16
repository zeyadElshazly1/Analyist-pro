"""
Preprocessing pipeline builder.

build_preprocessor(numeric_features, categorical_features) → ColumnTransformer

Replaces the original per-column LabelEncoder approach (which imposed false
ordinal ordering on categoricals) with OneHotEncoder inside a ColumnTransformer.
The returned transformer is designed to be the first step in an sklearn Pipeline
so that CV folds never see test-fold statistics.
"""
from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline as SKPipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def build_preprocessor(
    numeric_features: list[str],
    categorical_features: list[str],
) -> ColumnTransformer:
    """
    Return a ColumnTransformer that:
      - Numeric columns: median imputation → StandardScaler
      - Categorical columns: constant imputation → OneHotEncoder(handle_unknown='ignore')

    Passing an empty categorical_features list is safe — that transformer is omitted.
    """
    numeric_pipe = SKPipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
    ])
    transformers: list = [("num", numeric_pipe, numeric_features)]

    if categorical_features:
        cat_pipe = SKPipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value="(missing)")),
            ("ohe",     OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ])
        transformers.append(("cat", cat_pipe, categorical_features))

    return ColumnTransformer(transformers, remainder="drop")

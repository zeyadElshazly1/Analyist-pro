import pandas as pd
import numpy as np
from scipy import stats


def compare_columns(df: pd.DataFrame, col_a: str, col_b: str) -> dict:
    if col_a not in df.columns:
        raise ValueError(f"Column '{col_a}' not found")
    if col_b not in df.columns:
        raise ValueError(f"Column '{col_b}' not found")

    is_num_a = pd.api.types.is_numeric_dtype(df[col_a])
    is_num_b = pd.api.types.is_numeric_dtype(df[col_b])
    clean = df[[col_a, col_b]].dropna()

    if is_num_a and is_num_b:
        return _num_num(clean, col_a, col_b)
    elif not is_num_a and not is_num_b:
        return _cat_cat(clean, col_a, col_b)
    elif is_num_a and not is_num_b:
        return _num_cat(clean, col_a, col_b)
    else:
        return _num_cat(clean, col_b, col_a, swapped=True)


def _num_num(df, col_a, col_b):
    r, p = stats.pearsonr(df[col_a], df[col_b])
    return {
        "type": "numeric_vs_numeric",
        "col_a": col_a,
        "col_b": col_b,
        "correlation": round(float(r), 3),
        "p_value": round(float(p), 4),
        "significant": bool(p < 0.05),
        "scatter_data": df[[col_a, col_b]].head(300).to_dict(orient="records"),
    }


def _num_cat(df, num_col, cat_col, swapped=False):
    top_cats = df[cat_col].value_counts().head(10).index.tolist()
    df = df[df[cat_col].isin(top_cats)]

    group_stats = (
        df.groupby(cat_col)[num_col]
        .agg(["mean", "median", "std", "count"])
        .round(3)
        .reset_index()
    )
    group_stats.columns = ["category", "mean", "median", "std", "count"]
    group_stats = group_stats.sort_values("mean", ascending=False)

    return {
        "type": "numeric_vs_categorical",
        "num_col": num_col,
        "cat_col": cat_col,
        "swapped": swapped,
        "group_stats": group_stats.to_dict(orient="records"),
    }


def _cat_cat(df, col_a, col_b):
    top_a = df[col_a].value_counts().head(8).index.tolist()
    top_b = df[col_b].value_counts().head(8).index.tolist()
    df = df[df[col_a].isin(top_a) & df[col_b].isin(top_b)]

    crosstab = pd.crosstab(df[col_a], df[col_b], normalize="index").round(3)

    heatmap_data = [
        {"x": str(col_val), "y": str(row_val), "value": float(crosstab.loc[row_val, col_val])}
        for row_val in crosstab.index
        for col_val in crosstab.columns
    ]

    return {
        "type": "categorical_vs_categorical",
        "col_a": col_a,
        "col_b": col_b,
        "heatmap_data": heatmap_data,
        "col_a_values": [str(v) for v in top_a],
        "col_b_values": [str(v) for v in top_b],
    }

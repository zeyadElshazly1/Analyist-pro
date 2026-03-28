import pandas as pd
import numpy as np
from scipy import stats
from itertools import combinations


def build_correlation_matrix(df: pd.DataFrame) -> dict:
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_cols = [
        c for c in numeric_cols
        if not ("id" in c.lower() and df[c].nunique() > len(df) * 0.9)
    ]

    if len(numeric_cols) < 2:
        return {"columns": numeric_cols, "matrix": [], "pairs": []}

    sub = df[numeric_cols].dropna()
    corr = sub.corr(method="pearson")

    matrix = []
    for col_a in numeric_cols:
        row = {"column": col_a}
        for col_b in numeric_cols:
            row[col_b] = round(float(corr.loc[col_a, col_b]), 3)
        matrix.append(row)

    pairs = []
    for col_a, col_b in combinations(numeric_cols, 2):
        clean = df[[col_a, col_b]].dropna()
        if len(clean) < 5:
            continue
        r, p = stats.pearsonr(clean[col_a], clean[col_b])
        abs_r = abs(r)

        if abs_r < 0.1:
            strength = "Negligible"
        elif abs_r < 0.3:
            strength = "Weak"
        elif abs_r < 0.5:
            strength = "Moderate"
        elif abs_r < 0.7:
            strength = "Strong"
        else:
            strength = "Very strong"

        pairs.append({
            "col_a": col_a,
            "col_b": col_b,
            "r": round(float(r), 3),
            "p_value": round(float(p), 4),
            "strength": strength,
            "direction": "positive" if r > 0 else "negative",
            "significant": bool(p < 0.05),
        })

    pairs.sort(key=lambda x: abs(x["r"]), reverse=True)

    return {"columns": numeric_cols, "matrix": matrix, "pairs": pairs[:20]}

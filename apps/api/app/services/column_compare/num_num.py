"""Numeric vs numeric column comparison."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .stats import _distribution_overlap


def compare_num_num(df: pd.DataFrame, col_a: str, col_b: str) -> dict:
    n_total = len(df[[col_a, col_b]])
    clean = df[[col_a, col_b]].dropna()
    n_used = len(clean)
    if n_used < 5:
        raise ValueError("Not enough paired values for comparison")

    sample_loss = {
        "n_total": n_total,
        "n_used": n_used,
        "n_dropped": n_total - n_used,
        "pct_dropped": round((n_total - n_used) / max(n_total, 1) * 100, 1),
    }

    a = clean[col_a].to_numpy(dtype=float)
    b = clean[col_b].to_numpy(dtype=float)

    pearson_r, pearson_p = stats.pearsonr(a, b)
    spearman_r, spearman_p = stats.spearmanr(a, b)

    r_squared = round(float(pearson_r ** 2), 4)
    kendall_tau, kendall_p = stats.kendalltau(a, b)

    overlap = _distribution_overlap(a, b)

    regression = []
    coeffs = None
    if float(np.std(a)) > 1e-10 and float(np.std(b)) > 1e-10:
        try:
            coeffs = np.polyfit(a, b, 1)
            x_range = np.linspace(float(clean[col_a].min()), float(clean[col_a].max()), 50)
            regression = [
                {"x": round(float(x), 4), "y_hat": round(float(np.polyval(coeffs, x)), 4)}
                for x in x_range
            ]
        except (np.linalg.LinAlgError, Exception):
            coeffs = None

    # Vectorized scatter — no iterrows
    sample = clean.sample(min(n_used, 400), random_state=42)
    x_vals = sample[col_a].to_numpy(dtype=float)
    y_vals = sample[col_b].to_numpy(dtype=float)

    if coeffs is not None:
        predicted = np.polyval(coeffs, x_vals)
        residuals = y_vals - predicted
        resid_std = float(np.std(residuals))
        is_anomaly = (resid_std > 1e-10) & (np.abs(residuals) > 2 * resid_std)
    else:
        is_anomaly = np.zeros(len(x_vals), dtype=bool)

    scatter = [
        {"x": round(float(x), 4), "y": round(float(y), 4), "is_anomaly": bool(ia)}
        for x, y, ia in zip(x_vals, y_vals, is_anomaly)
    ]

    stronger_r = max(abs(pearson_r), abs(spearman_r))
    effect = "strong" if stronger_r > 0.7 else "moderate" if stronger_r > 0.4 else "weak"
    direction = "positive" if pearson_r > 0 else "negative"
    sig_text = "statistically significant" if pearson_p < 0.05 else "not statistically significant"

    interpretation = (
        f"Pearson r={pearson_r:.2f} ({effect} {direction} correlation, {sig_text}, p={pearson_p:.4f}). "
        f"R²={r_squared:.2f} — {col_a} explains {r_squared * 100:.0f}% of {col_b}'s variance. "
        f"Kendall τ={kendall_tau:.2f} (robust rank correlation). "
        f"Distribution overlap: {overlap * 100:.0f}% — "
        f"{'the two columns have very similar distributions' if overlap > 0.7 else 'the distributions diverge substantially' if overlap < 0.3 else 'moderate overlap between distributions'}."
    )

    return {
        "type": "num_num",
        "col_a": col_a,
        "col_b": col_b,
        "n": n_used,
        "pearson_r": round(float(pearson_r), 4),
        "pearson_p": round(float(pearson_p), 6),
        "spearman_r": round(float(spearman_r), 4),
        "spearman_p": round(float(spearman_p), 6),
        "cohens_d": None,
        "r_squared": r_squared,
        "kendall_tau": round(float(kendall_tau), 4),
        "kendall_p": round(float(kendall_p), 6),
        "effect_size": effect,
        "distribution_overlap": overlap,
        "interpretation": interpretation,
        "scatter": scatter,
        "regression_line": regression,
        "slope": round(float(coeffs[0]), 4) if coeffs is not None else None,
        "intercept": round(float(coeffs[1]), 4) if coeffs is not None else None,
        "sample_loss": sample_loss,
    }

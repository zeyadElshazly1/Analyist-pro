"""
Distribution fitting for numeric columns.

Tests Normal, Log-normal, Pareto, and Exponential distributions using the
Kolmogorov-Smirnov statistic (lower D = better fit) and returns the best
match with an optional log-transform hint.
"""
import numpy as np
import pandas as pd
from scipy import stats


def _fit_distribution(series: pd.Series) -> dict | None:
    """
    Fit a small set of candidate distributions and return the best fit.

    Tests: Normal, Log-normal (positive data only), Pareto (positive data only),
    Exponential (non-negative data only).
    Uses the Kolmogorov-Smirnov statistic — lower D = better fit.

    Returns a dict with ``best_fit``, ``ks_statistic``, and
    ``transform_hint`` if a non-normal fit is best.
    Returns None if the series is too small or all-constant.
    """
    clean = series.dropna()
    if len(clean) < 20 or clean.std() < 1e-10:
        return None

    candidates: list[tuple[str, float]] = []

    # Normal
    try:
        d, _ = stats.kstest(clean, "norm", args=(float(clean.mean()), float(clean.std())))
        candidates.append(("normal", float(d)))
    except Exception:
        pass

    # Log-normal — only valid for strictly positive data
    if float(clean.min()) > 0:
        try:
            log_data = np.log(clean)
            d, _ = stats.kstest(
                clean, "lognorm",
                args=(float(log_data.std()), 0, float(np.exp(log_data.mean())))
            )
            candidates.append(("lognormal", float(d)))
        except Exception:
            pass

        # Pareto
        try:
            shape, loc, scale = stats.pareto.fit(clean, floc=0)
            d, _ = stats.kstest(clean, "pareto", args=(shape, loc, scale))
            candidates.append(("pareto", float(d)))
        except Exception:
            pass

    # Exponential — for right-skewed non-negative data
    if float(clean.min()) >= 0:
        try:
            loc_e, scale_e = stats.expon.fit(clean, floc=0)
            d, _ = stats.kstest(clean, "expon", args=(loc_e, scale_e))
            candidates.append(("exponential", float(d)))
        except Exception:
            pass

    if not candidates:
        return None

    best_name, best_d = min(candidates, key=lambda x: x[1])

    transform_hints = {
        "lognormal":   "Log-transform (np.log) recommended before linear modeling",
        "pareto":      "Pareto-distributed — use percentile/quantile analysis; log-transform for regression",
        "exponential": "Exponential decay pattern — consider log-transform or survival analysis",
    }

    return {
        "best_fit": best_name,
        "ks_statistic": round(best_d, 4),
        "all_fits": {name: round(d, 4) for name, d in sorted(candidates, key=lambda x: x[1])},
        "transform_hint": transform_hints.get(best_name),
    }

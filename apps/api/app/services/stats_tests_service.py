from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def _effect_label(effect_size: float, metric: str) -> str:
    thresholds = {
        "cohens_d": [(0.2, "small"), (0.5, "medium"), (0.8, "large")],
        "cramers_v": [(0.1, "small"), (0.3, "medium"), (0.5, "large")],
        "eta_squared": [(0.01, "small"), (0.06, "medium"), (0.14, "large")],
        "r": [(0.1, "small"), (0.3, "medium"), (0.5, "large")],
    }
    abs_e = abs(effect_size)
    for threshold, label in thresholds.get(metric, []):
        if abs_e < threshold:
            return label
    return "large"


def _conclusion(p_value: float, alpha: float, effect_size: float, effect_metric: str, context: str = "") -> str:
    sig = p_value < alpha
    interp = _effect_label(effect_size, effect_metric)
    if sig:
        return (
            f"There is a statistically significant {context}(p={p_value:.4f}, α={alpha}). "
            f"The effect size is {interp} ({effect_metric.replace('_', ' ')}={abs(effect_size):.3f}), "
            f"suggesting this difference {'is' if interp in ('medium', 'large') else 'may not be'} practically meaningful."
        )
    return (
        f"No statistically significant {context}was detected (p={p_value:.4f}, α={alpha}). "
        f"The effect size is {interp} ({effect_metric.replace('_', ' ')}={abs(effect_size):.3f})."
    )


def run_test(
    df: pd.DataFrame,
    test_type: str,
    col_a: str,
    col_b: str | None = None,
    alpha: float = 0.05,
) -> dict:
    if col_a not in df.columns:
        raise ValueError(f"Column '{col_a}' not found.")
    if col_b is not None and col_b not in df.columns:
        raise ValueError(f"Column '{col_b}' not found.")

    result: dict = {"test_type": test_type, "alpha": alpha}

    if test_type == "ttest":
        if col_b is None:
            raise ValueError("col_b (grouping column) required for t-test.")
        groups = df.groupby(col_b)[col_a].apply(lambda x: x.dropna().values)
        if len(groups) != 2:
            raise ValueError("t-test requires exactly 2 groups.")
        g1, g2 = groups.iloc[0], groups.iloc[1]
        stat, p = stats.ttest_ind(g1, g2, equal_var=False)
        pooled_std = np.sqrt((np.std(g1, ddof=1) ** 2 + np.std(g2, ddof=1) ** 2) / 2)
        d = (np.mean(g1) - np.mean(g2)) / pooled_std if pooled_std > 0 else 0.0
        result.update({
            "statistic": round(float(stat), 4),
            "p_value": round(float(p), 6),
            "effect_size": round(float(d), 4),
            "effect_size_label": "Cohen's d",
            "effect_interpretation": _effect_label(d, "cohens_d"),
            "is_significant": bool(p < alpha),
            "conclusion": _conclusion(p, alpha, d, "cohens_d", "difference between groups "),
            "group_stats": [
                {"group": str(groups.index[0]), "n": len(g1), "mean": round(float(np.mean(g1)), 4), "std": round(float(np.std(g1, ddof=1)), 4)},
                {"group": str(groups.index[1]), "n": len(g2), "mean": round(float(np.mean(g2)), 4), "std": round(float(np.std(g2, ddof=1)), 4)},
            ],
            "sample_sizes": [len(g1), len(g2)],
        })

    elif test_type == "paired_ttest":
        if col_b is None:
            raise ValueError("col_b required for paired t-test.")
        a = df[col_a].dropna()
        b = df[col_b].dropna()
        common = a.index.intersection(b.index)
        a, b = a[common].values, b[common].values
        stat, p = stats.ttest_rel(a, b)
        d = np.mean(a - b) / np.std(a - b, ddof=1) if np.std(a - b, ddof=1) > 0 else 0.0
        result.update({
            "statistic": round(float(stat), 4),
            "p_value": round(float(p), 6),
            "effect_size": round(float(d), 4),
            "effect_size_label": "Cohen's d (paired)",
            "effect_interpretation": _effect_label(d, "cohens_d"),
            "is_significant": bool(p < alpha),
            "conclusion": _conclusion(p, alpha, d, "cohens_d", "paired difference "),
            "sample_sizes": [len(a)],
        })

    elif test_type == "anova":
        if col_b is None:
            raise ValueError("col_b (grouping column) required for ANOVA.")
        groups = df.groupby(col_b)[col_a].apply(lambda x: x.dropna().values)
        if len(groups) < 2:
            raise ValueError("ANOVA requires at least 2 groups.")
        stat, p = stats.f_oneway(*groups)
        # eta squared
        grand_mean = df[col_a].dropna().mean()
        ss_between = sum(len(g) * (np.mean(g) - grand_mean) ** 2 for g in groups)
        ss_total = sum(np.sum((g - grand_mean) ** 2) for g in groups)
        eta2 = float(ss_between / ss_total) if ss_total > 0 else 0.0
        result.update({
            "statistic": round(float(stat), 4),
            "p_value": round(float(p), 6),
            "effect_size": round(eta2, 4),
            "effect_size_label": "η² (eta-squared)",
            "effect_interpretation": _effect_label(eta2, "eta_squared"),
            "is_significant": bool(p < alpha),
            "conclusion": _conclusion(p, alpha, eta2, "eta_squared", "difference across groups "),
            "group_stats": [
                {"group": str(groups.index[i]), "n": len(g), "mean": round(float(np.mean(g)), 4), "std": round(float(np.std(g, ddof=1)), 4)}
                for i, g in enumerate(groups)
            ],
            "sample_sizes": [len(g) for g in groups],
        })

    elif test_type == "mannwhitney":
        if col_b is None:
            raise ValueError("col_b (grouping column) required for Mann-Whitney.")
        groups = df.groupby(col_b)[col_a].apply(lambda x: x.dropna().values)
        if len(groups) != 2:
            raise ValueError("Mann-Whitney requires exactly 2 groups.")
        g1, g2 = groups.iloc[0], groups.iloc[1]
        stat, p = stats.mannwhitneyu(g1, g2, alternative="two-sided")
        n = len(g1) + len(g2)
        z = (stat - len(g1) * len(g2) / 2) / np.sqrt(len(g1) * len(g2) * (n + 1) / 12)
        r = abs(z) / np.sqrt(n) if n > 0 else 0.0
        result.update({
            "statistic": round(float(stat), 4),
            "p_value": round(float(p), 6),
            "effect_size": round(float(r), 4),
            "effect_size_label": "r (rank-biserial)",
            "effect_interpretation": _effect_label(r, "r"),
            "is_significant": bool(p < alpha),
            "conclusion": _conclusion(p, alpha, r, "r", "rank-based difference "),
            "group_stats": [
                {"group": str(groups.index[0]), "n": len(g1), "median": round(float(np.median(g1)), 4)},
                {"group": str(groups.index[1]), "n": len(g2), "median": round(float(np.median(g2)), 4)},
            ],
            "sample_sizes": [len(g1), len(g2)],
        })

    elif test_type == "kruskal":
        if col_b is None:
            raise ValueError("col_b (grouping column) required for Kruskal-Wallis.")
        groups = df.groupby(col_b)[col_a].apply(lambda x: x.dropna().values)
        if len(groups) < 2:
            raise ValueError("Kruskal-Wallis requires at least 2 groups.")
        stat, p = stats.kruskal(*groups)
        n = sum(len(g) for g in groups)
        h_effect = float(stat) / (n - 1) if n > 1 else 0.0
        result.update({
            "statistic": round(float(stat), 4),
            "p_value": round(float(p), 6),
            "effect_size": round(h_effect, 4),
            "effect_size_label": "H / (n-1)",
            "effect_interpretation": _effect_label(h_effect, "eta_squared"),
            "is_significant": bool(p < alpha),
            "conclusion": _conclusion(p, alpha, h_effect, "eta_squared", "rank-based difference across groups "),
            "sample_sizes": [len(g) for g in groups],
        })

    elif test_type == "chi_square":
        if col_b is None:
            raise ValueError("col_b required for chi-square test.")
        ct = pd.crosstab(df[col_a], df[col_b])
        stat, p, dof, expected = stats.chi2_contingency(ct)
        n = ct.sum().sum()
        k = min(ct.shape) - 1
        v = float(np.sqrt(stat / (n * k))) if n * k > 0 else 0.0
        result.update({
            "statistic": round(float(stat), 4),
            "p_value": round(float(p), 6),
            "effect_size": round(v, 4),
            "effect_size_label": "Cramér's V",
            "effect_interpretation": _effect_label(v, "cramers_v"),
            "is_significant": bool(p < alpha),
            "conclusion": _conclusion(p, alpha, v, "cramers_v", "association between variables "),
            "degrees_of_freedom": int(dof),
            "sample_sizes": [int(n)],
            "crosstab": ct.to_dict(),
        })

    elif test_type == "shapiro":
        data = df[col_a].dropna().values
        if len(data) > 5000:
            rng = np.random.default_rng(42)
            data = rng.choice(data, 5000, replace=False)
        stat, p = stats.shapiro(data)
        result.update({
            "statistic": round(float(stat), 4),
            "p_value": round(float(p), 6),
            "effect_size": 0.0,
            "effect_size_label": "N/A",
            "effect_interpretation": "N/A",
            "is_significant": bool(p < alpha),
            "is_normal": bool(p >= alpha),
            "conclusion": (
                f"The data {'appears to be' if p >= alpha else 'does not appear to be'} normally distributed "
                f"(Shapiro-Wilk W={stat:.4f}, p={p:.4f})."
            ),
            "sample_sizes": [len(data)],
        })

    elif test_type == "levene":
        if col_b is None:
            raise ValueError("col_b (grouping column) required for Levene test.")
        groups = df.groupby(col_b)[col_a].apply(lambda x: x.dropna().values)
        if len(groups) < 2:
            raise ValueError("Levene test requires at least 2 groups.")
        stat, p = stats.levene(*groups)
        result.update({
            "statistic": round(float(stat), 4),
            "p_value": round(float(p), 6),
            "effect_size": 0.0,
            "effect_size_label": "N/A",
            "effect_interpretation": "N/A",
            "is_significant": bool(p < alpha),
            "equal_variances": bool(p >= alpha),
            "conclusion": (
                f"Variances are {'equal' if p >= alpha else 'not equal'} across groups "
                f"(Levene F={stat:.4f}, p={p:.4f}). "
                f"{'Use standard ANOVA.' if p >= alpha else 'Consider Welch ANOVA or non-parametric tests.'}"
            ),
            "sample_sizes": [len(g) for g in groups],
        })
    else:
        raise ValueError(f"Unknown test type: '{test_type}'. Valid: ttest, paired_ttest, anova, mannwhitney, kruskal, chi_square, shapiro, levene")

    return result


def power_analysis(
    effect_size: float,
    alpha: float = 0.05,
    power: float = 0.8,
    test_type: str = "ttest",
) -> dict:
    try:
        from statsmodels.stats.power import TTestIndPower, FTestAnovaPower

        if test_type in ("ttest", "paired_ttest", "mannwhitney"):
            analysis = TTestIndPower()
            n = analysis.solve_power(effect_size=effect_size, alpha=alpha, power=power)
        elif test_type in ("anova", "kruskal"):
            analysis = FTestAnovaPower()
            n = analysis.solve_power(effect_size=effect_size, alpha=alpha, power=power, k_groups=3)
        else:
            n = _approx_sample_size(effect_size, alpha, power)

        return {
            "required_n_per_group": int(np.ceil(n)),
            "effect_size": effect_size,
            "alpha": alpha,
            "power": power,
            "method": "statsmodels",
        }
    except ImportError:
        n = _approx_sample_size(effect_size, alpha, power)
        return {
            "required_n_per_group": int(np.ceil(n)),
            "effect_size": effect_size,
            "alpha": alpha,
            "power": power,
            "method": "approximation",
        }


def _approx_sample_size(effect_size: float, alpha: float, power: float) -> float:
    """Cohen's approximation for two-sample t-test sample size."""
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(power)
    if effect_size == 0:
        return float("inf")
    return (2 * ((z_alpha + z_beta) / effect_size) ** 2)

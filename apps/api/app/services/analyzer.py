import pandas as pd
import numpy as np
from scipy import stats
from itertools import combinations


def _bh_correct(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg FDR correction. Returns adjusted p-values."""
    n = len(p_values)
    if n == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [0.0] * n
    prev = 1.0
    for rank, (orig_idx, p) in enumerate(reversed(indexed), 1):
        adj = min(prev, p * n / (n - rank + 1))
        adjusted[orig_idx] = adj
        prev = adj
    return adjusted


def _normality_test(series: pd.Series) -> bool:
    """Returns True if series is approximately normal."""
    clean = series.dropna()
    if len(clean) < 8:
        return True
    try:
        if len(clean) <= 5000:
            _, p = stats.shapiro(clean.sample(min(len(clean), 2000), random_state=42))
        else:
            _, p = stats.normaltest(clean)
        return bool(p > 0.05)
    except Exception:
        return True


def _cohens_d(group_a: np.ndarray, group_b: np.ndarray) -> float:
    """Cohen's d effect size between two groups."""
    n_a, n_b = len(group_a), len(group_b)
    if n_a < 2 or n_b < 2:
        return 0.0
    pooled_std = np.sqrt(
        ((n_a - 1) * group_a.std() ** 2 + (n_b - 1) * group_b.std() ** 2)
        / (n_a + n_b - 2)
    )
    if pooled_std < 1e-10:
        return 0.0
    return float((group_a.mean() - group_b.mean()) / pooled_std)


def _isolation_forest_anomalies(df: pd.DataFrame, numeric_cols: list[str]) -> set:
    """
    Detect multivariate anomalies using Isolation Forest.
    Returns a set of row indices flagged as anomalous.
    """
    if len(numeric_cols) < 2:
        return set()
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        return set()

    sub = df[numeric_cols].dropna()
    if len(sub) < 20:
        return set()

    contamination = min(0.1, max(0.01, 1 / len(sub) * 10))
    clf = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
    preds = clf.fit_predict(sub)
    anomaly_indices = set(sub.index[preds == -1].tolist())
    return anomaly_indices


def analyze_dataset(df: pd.DataFrame) -> list[dict]:
    insights = []

    # Exclude ID-like columns
    id_cols = [
        col for col in df.columns
        if "id" in col.lower() and df[col].nunique() / max(len(df), 1) > 0.95
    ]
    df = df.drop(columns=id_cols, errors="ignore")

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = [
        col for col in df.select_dtypes(include=["object", "category"]).columns
        if df[col].nunique() < 50
    ]

    # ── 1. Correlation insights (Pearson or Spearman based on normality) ──────
    # Threshold lowered to r > 0.3 (from 0.4) for more coverage, gated by adj_p
    pairs = list(combinations(numeric_cols, 2))
    raw_corr_data = []
    for col1, col2 in pairs:
        clean = df[[col1, col2]].dropna()
        if len(clean) < 10:
            continue
        is_normal = _normality_test(clean[col1]) and _normality_test(clean[col2])
        if is_normal:
            corr, pvalue = stats.pearsonr(clean[col1], clean[col2])
            method = "Pearson"
        else:
            corr, pvalue = stats.spearmanr(clean[col1], clean[col2])
            method = "Spearman"
        if abs(corr) > 0.3:
            raw_corr_data.append((col1, col2, corr, pvalue, method, len(clean)))

    if raw_corr_data:
        pvals = [x[3] for x in raw_corr_data]
        adj_pvals = _bh_correct(pvals)
        for (col1, col2, corr, _, method, n), adj_p in zip(raw_corr_data, adj_pvals):
            if abs(corr) > 0.3 and adj_p < 0.05:
                direction = "positively" if corr > 0 else "negatively"
                strength = (
                    "very strongly" if abs(corr) > 0.9
                    else "strongly" if abs(corr) > 0.7
                    else "moderately" if abs(corr) > 0.5
                    else "weakly"
                )
                severity = "high" if abs(corr) > 0.7 else "medium"
                insights.append({
                    "type": "correlation",
                    "severity": severity,
                    "confidence": round(abs(corr) * 100, 1),
                    "title": f"Relationship detected: {col1} & {col2}",
                    "finding": (
                        f"{col1} and {col2} are {strength} {direction} correlated "
                        f"(r={corr:.2f}, {method}). When {col1} increases, {col2} tends to "
                        f"{'increase' if corr > 0 else 'decrease'}."
                    ),
                    "evidence": f"{method} r={corr:.3f}, adjusted p={adj_p:.4f}, n={n}",
                    "action": (
                        f"Investigate whether {col1} drives {col2}. Consider multicollinearity "
                        f"if both are used as model features."
                    ),
                })

    # ── 2. Multivariate anomaly detection (Isolation Forest) ─────────────────
    if len(numeric_cols) >= 2:
        anomaly_indices = _isolation_forest_anomalies(df, numeric_cols)
        anomaly_count = len(anomaly_indices)
        if anomaly_count > 0:
            anomaly_pct = round(anomaly_count / len(df) * 100, 1)
            severity = "high" if anomaly_pct > 5 else "medium"
            insights.append({
                "type": "anomaly",
                "severity": severity,
                "confidence": round(min(95, 70 + anomaly_pct * 2), 1),
                "title": f"Multivariate anomalies detected ({anomaly_count} rows)",
                "finding": (
                    f"{anomaly_count} records ({anomaly_pct}% of data) show unusual combinations "
                    f"of values across {len(numeric_cols)} numeric columns — flagged by Isolation Forest."
                ),
                "evidence": (
                    f"Isolation Forest (contamination auto), {len(numeric_cols)} features, "
                    f"{anomaly_count} anomalous rows"
                ),
                "action": (
                    f"Inspect the {anomaly_count} flagged rows — they may represent data entry errors, "
                    f"fraud signals, or genuinely extreme cases worth investigating."
                ),
            })

    # ── 3. Univariate anomaly detection (adaptive Z-score / IQR) ─────────────
    for col in numeric_cols:
        col_data = df[col].dropna()
        if len(col_data) < 10:
            continue
        skew = abs(float(col_data.skew()))
        if skew > 1.5:
            # Use IQR for heavily skewed distributions — Z-score is unreliable
            q1, q3 = float(col_data.quantile(0.25)), float(col_data.quantile(0.75))
            iqr = q3 - q1
            if iqr <= 0:
                continue
            lower = q1 - 3.0 * iqr
            upper = q3 + 3.0 * iqr
            outlier_mask = (col_data < lower) | (col_data > upper)
            outlier_count = int(outlier_mask.sum())
            method_label = "IQR (3× fence)"
            evidence_detail = f"IQR fence [{lower:.3g}, {upper:.3g}], skew={skew:.2f}"
        else:
            z_scores = np.abs(stats.zscore(col_data))
            outlier_count = int((z_scores > 3).sum())
            worst_z = round(float(z_scores.max()), 1)
            method_label = "Z-score (±3σ)"
            evidence_detail = f"Max Z-score: {worst_z}. Mean: {col_data.mean():.2f}, Std: {col_data.std():.2f}"

        if outlier_count > 0:
            outlier_pct = round(outlier_count / len(col_data) * 100, 1)
            severity = "high" if outlier_pct > 5 else "medium"
            insights.append({
                "type": "anomaly",
                "severity": severity,
                "confidence": round(min(97, 75 + outlier_pct * 2), 1),
                "title": f"Anomalies in {col}",
                "finding": (
                    f"{outlier_count} records ({outlier_pct}% of data) in '{col}' are statistical "
                    f"outliers using {method_label}."
                ),
                "evidence": evidence_detail,
                "action": (
                    f"Review the {outlier_count} extreme values in '{col}'. "
                    f"They could represent data entry errors, fraud, or your most extreme cases."
                ),
            })

    # ── 4. Distribution skewness insights ─────────────────────────────────────
    for col in numeric_cols:
        col_data = df[col].dropna()
        if len(col_data) < 20:
            continue
        skew = float(col_data.skew())
        if abs(skew) > 1.5:
            direction = "right (positive)" if skew > 0 else "left (negative)"
            insights.append({
                "type": "distribution",
                "severity": "medium",
                "confidence": round(min(95, 60 + abs(skew) * 8), 1),
                "title": f"Skewed distribution: {col}",
                "finding": (
                    f"'{col}' is heavily skewed {direction} (skewness={skew:.2f}). "
                    f"Most values cluster at the {'low' if skew > 0 else 'high'} end."
                ),
                "evidence": f"Skewness={skew:.3f}, Mean={col_data.mean():.2f}, Median={col_data.median():.2f}",
                "action": (
                    f"Consider log-transforming '{col}' before modeling or statistical tests. "
                    f"The gap between mean ({col_data.mean():.2f}) and median ({col_data.median():.2f}) confirms skew."
                ),
            })

    # ── 5. Segment gap analysis with Welch's t-test + Cohen's d ──────────────
    for cat_col in categorical_cols:
        for num_col in numeric_cols:
            group_data = {
                name: grp.dropna().values
                for name, grp in df.groupby(cat_col)[num_col]
            }
            # Require min 30 rows per group for reliable statistics
            valid_groups = {k: v for k, v in group_data.items() if len(v) >= 30}
            if len(valid_groups) < 2:
                continue

            group_means = {k: np.mean(v) for k, v in valid_groups.items()}
            max_group = max(group_means, key=group_means.get)
            min_group = min(group_means, key=group_means.get)

            if group_means[min_group] == 0:
                continue
            ratio = group_means[max_group] / group_means[min_group]
            if ratio <= 1.5:
                continue

            # Welch's t-test (sample-size-aware, no equal-variance assumption)
            _, welch_p = stats.ttest_ind(
                valid_groups[max_group], valid_groups[min_group],
                equal_var=False
            )
            if welch_p >= 0.05:
                continue

            # Cohen's d effect size
            d = _cohens_d(valid_groups[max_group], valid_groups[min_group])
            effect_label = (
                "large" if abs(d) >= 0.8
                else "medium" if abs(d) >= 0.5
                else "small"
            )
            severity = "high" if ratio > 3 and abs(d) >= 0.5 else "medium"

            insights.append({
                "type": "segment",
                "severity": severity,
                "confidence": round(min(95, 55 + ratio * 4), 1),
                "title": f"Segment gap: {cat_col} → {num_col}",
                "finding": (
                    f"'{max_group}' has {ratio:.1f}x higher average {num_col} than '{min_group}' "
                    f"({group_means[max_group]:.2f} vs {group_means[min_group]:.2f})."
                ),
                "evidence": (
                    f"Welch's t-test p={welch_p:.4f}, Cohen's d={d:.2f} ({effect_label} effect), "
                    f"ratio={ratio:.2f}x, groups n={len(valid_groups[max_group])}/{len(valid_groups[min_group])}"
                ),
                "action": (
                    f"Prioritize or investigate '{max_group}' in '{cat_col}' — "
                    f"it significantly outperforms '{min_group}' on {num_col} "
                    f"with a {effect_label} effect size."
                ),
            })

    # ── 6. Binary categorical rate analysis ───────────────────────────────────
    binary_cols = [col for col in categorical_cols if df[col].nunique() == 2]
    for target_col in binary_cols:
        vals = df[target_col].dropna().unique()
        if len(vals) != 2:
            continue
        for cat_col in categorical_cols:
            if cat_col == target_col or df[cat_col].nunique() < 2:
                continue
            rates = df.groupby(cat_col)[target_col].apply(
                lambda x: (x == vals[0]).mean()
            ).dropna()
            group_sizes = df.groupby(cat_col)[target_col].count()
            # Only include groups with min 20 rows
            large_groups = group_sizes[group_sizes >= 20].index
            rates = rates[rates.index.isin(large_groups)]
            if len(rates) < 2:
                continue
            max_group = rates.idxmax()
            min_group = rates.idxmin()
            if rates[min_group] == 0:
                continue
            ratio = rates[max_group] / rates[min_group]
            if ratio > 1.8:
                insights.append({
                    "type": "segment",
                    "severity": "high" if ratio > 4 else "medium",
                    "confidence": round(min(95, 55 + ratio * 5), 1),
                    "title": f"Rate gap: {cat_col} → {target_col}",
                    "finding": (
                        f"'{max_group}' has {ratio:.1f}x higher '{vals[0]}' rate than '{min_group}' "
                        f"({rates[max_group]:.1%} vs {rates[min_group]:.1%})."
                    ),
                    "evidence": f"Rate ratio={ratio:.2f}x across {len(rates)} segments (min 20 rows per group)",
                    "action": (
                        f"'{max_group}' in '{cat_col}' shows dramatically different '{target_col}' behavior "
                        f"— consider targeting it separately."
                    ),
                })

    # ── 7. High-cardinality categorical columns ───────────────────────────────
    for col in df.select_dtypes(include=["object", "category"]).columns:
        n_unique = df[col].nunique()
        n_rows = len(df)
        ratio = n_unique / n_rows
        if ratio > 0.8 and n_unique > 50:
            insights.append({
                "type": "data_quality",
                "severity": "low",
                "confidence": 90.0,
                "title": f"High-cardinality column: {col}",
                "finding": (
                    f"'{col}' has {n_unique} unique values ({ratio:.0%} of rows). "
                    f"This column may be an identifier or free-text field."
                ),
                "evidence": f"{n_unique} unique values out of {n_rows} rows",
                "action": (
                    f"Consider whether '{col}' should be excluded from analysis, "
                    f"or if it needs to be bucketed/encoded."
                ),
            })

    # ── 8. Missing data patterns ──────────────────────────────────────────────
    missing = df.isnull().sum()
    for col, count in missing[missing > 0].items():
        pct = round(count / len(df) * 100, 1)
        if pct > 5:
            severity = "high" if pct > 30 else "medium"
            insights.append({
                "type": "data_quality",
                "severity": severity,
                "confidence": 99.0,
                "title": f"Missing data in {col}",
                "finding": f"{count} records ({pct}% of data) are missing values in '{col}'.",
                "evidence": f"{count}/{len(df)} rows missing ({pct}%)",
                "action": (
                    f"Investigate why '{col}' is missing for {pct}% of records. "
                    f"{'Drop this column or impute carefully.' if pct > 40 else 'Impute with median/mode or model-based imputation.'}"
                ),
            })

    # ── 9. Constant / near-constant columns ──────────────────────────────────
    for col in numeric_cols:
        col_data = df[col].dropna()
        if len(col_data) < 5:
            continue
        if col_data.std() < 1e-6:
            insights.append({
                "type": "data_quality",
                "severity": "medium",
                "confidence": 100.0,
                "title": f"Constant column: {col}",
                "finding": f"'{col}' has zero variance — all values are identical ({col_data.iloc[0]}).",
                "evidence": f"Std={col_data.std():.2e}, unique values={col_data.nunique()}",
                "action": f"Remove '{col}' from any model or analysis — it carries no information.",
            })

    # Sort: high severity first, then by confidence descending
    severity_order = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda x: (severity_order.get(x.get("severity", "low"), 2), -x["confidence"]))
    return insights[:15]


def get_dataset_summary(df: pd.DataFrame) -> dict:
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "numeric_cols": len(df.select_dtypes(include=[np.number]).columns),
        "categorical_cols": len(df.select_dtypes(include=["object"]).columns),
        "datetime_cols": len(df.select_dtypes(include=["datetime64"]).columns),
        "missing_pct": round(df.isnull().sum().sum() / max(len(df) * len(df.columns), 1) * 100, 1),
    }

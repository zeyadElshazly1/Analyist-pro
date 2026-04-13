import pandas as pd
import numpy as np
from scipy import stats
from itertools import combinations


def _bh_correct(p_values: list[float]) -> list[float]:
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
    na, nb = len(group_a), len(group_b)
    if na < 2 or nb < 2:
        return 0.0
    pooled_std = np.sqrt(
        ((na - 1) * group_a.std() ** 2 + (nb - 1) * group_b.std() ** 2) / (na + nb - 2)
    )
    return float((group_a.mean() - group_b.mean()) / pooled_std) if pooled_std > 1e-10 else 0.0


def _isolation_forest_anomalies(df: pd.DataFrame, numeric_cols: list[str]) -> set:
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
    return set(sub.index[preds == -1].tolist())


def _concentration_risk(df: pd.DataFrame, numeric_cols: list, categorical_cols: list) -> list[dict]:
    """
    Pareto concentration analysis:
    - Numeric: does the top 10/20% of a column account for a disproportionate share?
    - Categorical: does one category dominate heavily?
    """
    insights = []
    for num_col in numeric_cols[:5]:
        col = df[num_col].dropna()
        if len(col) < 20 or col.min() < 0:
            continue
        total = float(col.sum())
        if total <= 0:
            continue
        sorted_col = col.sort_values(ascending=False)
        top10_threshold = int(len(col) * 0.1)
        top20_threshold = int(len(col) * 0.2)
        top10_share = float(sorted_col.iloc[:top10_threshold].sum() / total * 100)
        top20_share = float(sorted_col.iloc[:top20_threshold].sum() / total * 100)

        if top10_share > 50:
            insights.append({
                "type": "concentration",
                "severity": "high" if top10_share > 70 else "medium",
                "confidence": round(min(95, 60 + top10_share * 0.4), 1),
                "title": f"Concentration risk in {num_col}",
                "finding": (
                    f"Top 10% of records account for {top10_share:.1f}% of total {num_col}. "
                    f"Top 20% account for {top20_share:.1f}%. Strong Pareto concentration detected."
                ),
                "evidence": f"Top 10%: {top10_share:.1f}%, Top 20%: {top20_share:.1f}% of total {num_col}",
                "action": (
                    f"Segment analysis around the top {top10_threshold} records in {num_col}. "
                    f"Consider whether this concentration represents risk or opportunity."
                ),
            })

    for cat_col in categorical_cols[:5]:
        counts = df[cat_col].value_counts()
        if len(counts) < 2:
            continue
        top_share = float(counts.iloc[0] / len(df) * 100)
        if top_share > 70:
            insights.append({
                "type": "concentration",
                "severity": "medium",
                "confidence": 90.0,
                "title": f"Category dominance: {cat_col}",
                "finding": (
                    f"'{counts.index[0]}' accounts for {top_share:.1f}% of all records in '{cat_col}'. "
                    f"This heavy imbalance can bias models and aggregations."
                ),
                "evidence": f"{counts.index[0]}: {int(counts.iloc[0])} of {len(df)} rows ({top_share:.1f}%)",
                "action": (
                    f"Check whether '{counts.index[0]}' over-representation is a data collection artifact. "
                    f"Consider stratified analysis for the minority categories."
                ),
            })

    return insights


def _interaction_effects(
    df: pd.DataFrame,
    numeric_cols: list,
    categorical_cols: list,
) -> list[dict]:
    """
    Detect interaction effects: 'the relationship between X and Y differs for high vs low Z.'
    For each significant numeric pair, split by a categorical moderator and compare r values.
    """
    insights = []
    if len(numeric_cols) < 2 or not categorical_cols:
        return []

    # Use top 3 numeric pairs by correlation magnitude
    pair_corrs = []
    for c1, c2 in combinations(numeric_cols[:6], 2):
        clean = df[[c1, c2]].dropna()
        if len(clean) < 20:
            continue
        try:
            r, _ = stats.pearsonr(clean[c1], clean[c2])
            if abs(r) > 0.25:
                pair_corrs.append((c1, c2, float(r)))
        except Exception:
            pass
    pair_corrs.sort(key=lambda x: abs(x[2]), reverse=True)

    for c1, c2, overall_r in pair_corrs[:3]:
        for mod_col in categorical_cols[:3]:
            group_corrs = {}
            for cat_val, group in df.groupby(mod_col):
                sub = group[[c1, c2]].dropna()
                if len(sub) < 15:
                    continue
                try:
                    r, _ = stats.pearsonr(sub[c1], sub[c2])
                    group_corrs[str(cat_val)] = float(r)
                except Exception:
                    pass

            if len(group_corrs) < 2:
                continue
            r_vals = list(group_corrs.values())
            r_range = max(r_vals) - min(r_vals)

            # Meaningful interaction: r varies by more than 0.3 across groups
            if r_range > 0.3:
                max_group = max(group_corrs, key=group_corrs.get)
                min_group = min(group_corrs, key=group_corrs.get)
                insights.append({
                    "type": "interaction",
                    "severity": "high" if r_range > 0.5 else "medium",
                    "confidence": round(min(90, 60 + r_range * 60), 1),
                    "title": f"Interaction effect: {c1} × {c2} moderated by {mod_col}",
                    "finding": (
                        f"The relationship between '{c1}' and '{c2}' (overall r={overall_r:.2f}) "
                        f"varies substantially by '{mod_col}': r={group_corrs[max_group]:.2f} for '{max_group}' "
                        f"vs r={group_corrs[min_group]:.2f} for '{min_group}'."
                    ),
                    "evidence": (
                        f"Correlation range across {mod_col} groups: {r_range:.2f}. "
                        f"Groups: {', '.join(f'{k}={v:.2f}' for k, v in group_corrs.items())}"
                    ),
                    "action": (
                        f"Analyze '{c1}' vs '{c2}' separately for each '{mod_col}' group. "
                        f"A model built on the overall correlation may be misleading."
                    ),
                })

    return insights[:3]


def _simpsons_paradox_hints(
    df: pd.DataFrame,
    numeric_cols: list,
    categorical_cols: list,
) -> list[dict]:
    """
    Simpson's paradox hint: overall trend reverses within subgroups.
    Checks if the sign of correlation between two numerics flips in a subgroup.
    """
    insights = []
    if len(numeric_cols) < 2 or not categorical_cols:
        return []

    for c1, c2 in combinations(numeric_cols[:4], 2):
        clean = df[[c1, c2]].dropna()
        if len(clean) < 20:
            continue
        try:
            overall_r, _ = stats.pearsonr(clean[c1], clean[c2])
        except Exception:
            continue
        if abs(overall_r) < 0.15:
            continue

        for cat_col in categorical_cols[:3]:
            flip_count = 0
            for _, group in df.groupby(cat_col):
                sub = group[[c1, c2]].dropna()
                if len(sub) < 10:
                    continue
                try:
                    r, _ = stats.pearsonr(sub[c1], sub[c2])
                    if (r > 0 and overall_r < 0) or (r < 0 and overall_r > 0):
                        flip_count += 1
                except Exception:
                    pass

            if flip_count >= 2:
                insights.append({
                    "type": "simpsons_paradox",
                    "severity": "high",
                    "confidence": 80.0,
                    "title": f"Possible Simpson's Paradox: {c1} vs {c2} by {cat_col}",
                    "finding": (
                        f"Overall, '{c1}' and '{c2}' have r={overall_r:.2f}, but within "
                        f"{flip_count} subgroups of '{cat_col}' the relationship reverses direction. "
                        f"This is a warning sign of Simpson's Paradox."
                    ),
                    "evidence": f"Overall r={overall_r:.2f}, {flip_count} subgroups show opposite sign",
                    "action": (
                        f"Always segment by '{cat_col}' when analyzing '{c1}' vs '{c2}'. "
                        f"The overall correlation is misleading — it is driven by group composition, not the true relationship."
                    ),
                })

    return insights[:2]


def _missing_data_patterns(df: pd.DataFrame, numeric_cols: list) -> list[dict]:
    """Detect structural missing data patterns."""
    insights = []
    missing_cols = [col for col in df.columns if df[col].isnull().any()]
    if not missing_cols:
        return []

    for miss_col in missing_cols[:5]:
        miss_indicator = df[miss_col].isnull().astype(int)
        for num_col in numeric_cols[:10]:
            if num_col == miss_col:
                continue
            other = df[num_col].fillna(df[num_col].median())
            try:
                from scipy.stats import pointbiserialr
                r, p = pointbiserialr(miss_indicator, other)
                if abs(r) > 0.35 and p < 0.05:
                    insights.append({
                        "type": "missing_pattern",
                        "severity": "medium",
                        "confidence": round(abs(r) * 100, 1),
                        "title": f"Structural missing data: {miss_col} linked to {num_col}",
                        "finding": (
                            f"'{miss_col}' is {'more' if r > 0 else 'less'} likely to be missing "
                            f"when '{num_col}' is {'high' if r > 0 else 'low'} (r={r:.2f}). "
                            f"This is a MAR or MNAR pattern, not random missingness."
                        ),
                        "evidence": f"Point-biserial r={r:.3f}, p={p:.4f} between missingness indicator and {num_col}",
                        "action": (
                            f"Do not use simple mean/median imputation for '{miss_col}'. "
                            f"Use model-based imputation (KNN or MICE) conditioned on '{num_col}'."
                        ),
                    })
                    break
            except Exception:
                pass

    return insights[:3]


def _trend_analysis(df: pd.DataFrame, numeric_cols: list) -> list[dict]:
    """
    Detect statistically significant monotonic trends in numeric columns.

    Uses linear regression over:
    - The datetime column (if one exists) — converted to ordinal days so the
      slope is expressed in units-per-day.
    - Otherwise the integer row index (trend relative to current data order).

    Reports only when p < 0.05 AND R² > 0.15 to filter out noise.
    """
    if not numeric_cols or len(df) < 10:
        return []

    datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
    if datetime_cols:
        time_col = datetime_cols[0]
        x = (df[time_col] - df[time_col].min()).dt.days.values.astype(float)
        time_label = f"over time (by '{time_col}')"
        unit_label = "per day"
    else:
        x = np.arange(len(df), dtype=float)
        time_label = "across row order"
        unit_label = "per row"

    insights = []
    for col in numeric_cols[:15]:
        col_data = df[col]
        valid = col_data.notna()
        y = col_data[valid].values.astype(float)
        x_clean = x[valid.values] if len(x) == len(df) else x[:len(y)]
        if len(y) < 10:
            continue
        try:
            slope, intercept, r, p, _ = stats.linregress(x_clean, y)
        except Exception:
            continue
        r2 = r ** 2
        if p >= 0.05 or r2 < 0.15:
            continue

        direction = "upward" if slope > 0 else "downward"
        pct_change = abs(slope) * (x_clean[-1] - x_clean[0]) / max(abs(float(np.mean(y))), 1e-10) * 100

        insights.append({
            "type": "trend",
            "severity": "high" if r2 > 0.5 else "medium",
            "confidence": round(min(97, r2 * 100), 1),
            "title": f"Trend detected: {col} ({direction})",
            "finding": (
                f"'{col}' shows a significant {direction} trend {time_label} "
                f"(slope={slope:+.4g} {unit_label}, R²={r2:.2f}). "
                f"Total change across the dataset: ~{pct_change:.1f}%."
            ),
            "evidence": (
                f"OLS slope={slope:+.4g} {unit_label}, R²={r2:.3f}, p={p:.4f}, n={len(y)}"
            ),
            "action": (
                f"Investigate the driver of the {direction} trend in '{col}'. "
                + ("Consider detrending before correlation analysis to avoid spurious relationships."
                   if r2 > 0.3 else "Monitor whether this trend continues.")
            ),
        })

    # Return at most 3 trend insights sorted by R²
    insights.sort(key=lambda x: x["confidence"], reverse=True)
    return insights[:3]


def _multicollinearity(df: pd.DataFrame, numeric_cols: list) -> list[dict]:
    """
    Detect multicollinearity using Variance Inflation Factor (VIF).

    VIF > 5 → moderate concern; VIF > 10 → severe.
    Only runs when there are ≥ 3 complete numeric columns with sufficient
    non-missing data, since VIF requires a full design matrix.
    """
    if len(numeric_cols) < 3:
        return []

    # Keep columns with < 30% missing
    usable = [c for c in numeric_cols if df[c].isnull().mean() < 0.3]
    if len(usable) < 3:
        return []

    sub = df[usable].dropna()
    if len(sub) < max(20, len(usable) * 2):
        return []

    # Remove constant columns — VIF is undefined for them
    usable = [c for c in usable if sub[c].std() > 1e-10]
    if len(usable) < 3:
        return []

    sub = sub[usable]

    try:
        from statsmodels.stats.outliers_influence import variance_inflation_factor
        X = sub.values
        vif_scores = {
            usable[i]: float(variance_inflation_factor(X, i))
            for i in range(len(usable))
        }
    except Exception:
        return []

    high_vif = {col: v for col, v in vif_scores.items() if v > 5}
    if not high_vif:
        return []

    severe = {col: v for col, v in high_vif.items() if v > 10}
    moderate = {col: v for col, v in high_vif.items() if 5 < v <= 10}

    severity = "high" if severe else "medium"
    affected = sorted(high_vif.items(), key=lambda x: x[1], reverse=True)
    top_cols = ", ".join(f"{c} (VIF={v:.1f})" for c, v in affected[:4])

    finding_parts = []
    if severe:
        s_cols = ", ".join(f"'{c}'" for c in severe)
        finding_parts.append(f"{len(severe)} column(s) have severe multicollinearity (VIF > 10): {s_cols}.")
    if moderate:
        m_cols = ", ".join(f"'{c}'" for c in moderate)
        finding_parts.append(f"{len(moderate)} column(s) have moderate multicollinearity (VIF 5–10): {m_cols}.")

    return [{
        "type": "multicollinearity",
        "severity": severity,
        "confidence": round(min(95, 70 + len(high_vif) * 5), 1),
        "title": f"Multicollinearity detected ({len(high_vif)} columns)",
        "finding": " ".join(finding_parts) + (
            " Including all of these as features in a model will produce unstable, "
            "hard-to-interpret coefficients."
        ),
        "evidence": f"VIF scores: {top_cols}",
        "action": (
            "Remove or combine redundant columns before modeling. "
            "Consider PCA to reduce correlated features into orthogonal components, "
            "or drop the column with the highest VIF and re-check."
        ),
    }]


def _leading_indicators(df: pd.DataFrame, numeric_cols: list) -> list[dict]:
    """
    Detect leading indicators: X at time t predicts Y at time t+k.
    Uses cross-correlation (lag analysis) between numeric columns.

    Only runs when a datetime column is present — otherwise row order is
    arbitrary and lag correlations are meaningless.  The DataFrame is sorted
    by the datetime column before analysis.
    """
    if len(numeric_cols) < 2 or len(df) < 20:
        return []

    # Require a datetime column so that row order is meaningful
    datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
    if not datetime_cols:
        return []

    # Sort by the first datetime column so lag analysis is time-ordered
    time_col = datetime_cols[0]
    df = df.sort_values(time_col).reset_index(drop=True)

    insights = []
    max_lag = min(5, len(df) // 4)

    for c1, c2 in combinations(numeric_cols[:5], 2):
        clean = df[[c1, c2]].dropna().reset_index(drop=True)
        if len(clean) < 20:
            continue

        best_lag = 0
        best_r = 0.0
        base_r, _ = stats.pearsonr(clean[c1], clean[c2])

        for lag in range(1, max_lag + 1):
            a = clean[c1].iloc[:-lag].values
            b = clean[c2].iloc[lag:].values
            if len(a) < 10:
                continue
            try:
                r, _ = stats.pearsonr(a, b)
                if abs(r) > abs(best_r) and abs(r) > abs(base_r) + 0.1:
                    best_r = r
                    best_lag = lag
            except Exception:
                pass

        if best_lag > 0 and abs(best_r) > 0.4:
            insights.append({
                "type": "leading_indicator",
                "severity": "medium",
                "confidence": round(abs(best_r) * 100, 1),
                "title": f"Leading indicator: {c1} → {c2} (lag {best_lag})",
                "finding": (
                    f"'{c1}' at time T correlates with '{c2}' at time T+{best_lag} "
                    f"(r={best_r:.2f} at lag {best_lag}, vs r={base_r:.2f} at lag 0). "
                    f"'{c1}' may be a leading indicator of '{c2}'."
                ),
                "evidence": (
                    f"Cross-correlation at lag={best_lag}: r={best_r:.3f} (baseline: r={base_r:.3f}). "
                    f"Data sorted by '{time_col}'."
                ),
                "action": (
                    f"Monitor '{c1}' as an early warning signal for '{c2}'. "
                    f"Changes in '{c1}' may precede changes in '{c2}' by {best_lag} periods."
                ),
                "note": f"Rows sorted by '{time_col}' for this analysis.",
            })

    return insights[:2]


def _generate_narrative(insights: list[dict], df: pd.DataFrame) -> str:
    """
    Generate a 3-paragraph executive summary connecting the insights.
    """
    n_rows, n_cols = len(df), len(df.columns)
    missing_pct = round(df.isnull().sum().sum() / max(n_rows * n_cols, 1) * 100, 1)

    high_sev = [i for i in insights if i.get("severity") == "high"]
    correlations = [i for i in insights if i["type"] == "correlation"]
    anomalies = [i for i in insights if i["type"] == "anomaly"]
    segments = [i for i in insights if i["type"] == "segment"]
    concentration = [i for i in insights if i["type"] == "concentration"]
    interactions = [i for i in insights if i["type"] == "interaction"]
    leading = [i for i in insights if i["type"] == "leading_indicator"]

    # Paragraph 1: Data quality overview
    if missing_pct > 5:
        quality_text = f"The dataset ({n_rows:,} rows × {n_cols} columns) has {missing_pct}% missing values, which may limit the reliability of some findings."
    else:
        quality_text = f"The dataset ({n_rows:,} rows × {n_cols} columns) is largely complete ({missing_pct}% missing values), supporting confident analysis."

    para1 = quality_text
    if anomalies:
        para1 += f" {len(anomalies)} column(s) contain statistical outliers that warrant review before modeling."

    # Paragraph 2: Key patterns and relationships
    parts = []
    if correlations:
        top_corr = correlations[0]
        parts.append(f"The strongest relationship is {top_corr['title'].replace('Relationship detected: ', '')}: {top_corr['finding'].split('.')[0]}.")
    if segments:
        top_seg = segments[0]
        parts.append(f"Segment analysis reveals: {top_seg['finding'].split('.')[0]}.")
    if concentration:
        top_conc = concentration[0]
        parts.append(top_conc["finding"].split(".")[0] + ".")
    if interactions:
        parts.append(f"Interaction effects detected in {len(interactions)} variable pair(s) — relationships vary by subgroup.")

    para2 = " ".join(parts) if parts else "No strong relationships or segment gaps were detected in this dataset."

    # Paragraph 3: Recommended actions
    actions = []
    if high_sev:
        actions.append(f"Address the {len(high_sev)} high-severity finding(s) first, particularly: {high_sev[0]['title']}.")
    if leading:
        actions.append(f"Explore leading indicators: {leading[0]['title']}.")
    if interactions:
        actions.append("Segment analyses by moderating variables to avoid misleading aggregate conclusions.")
    if not actions:
        actions.append("No urgent actions required. Continue monitoring for data drift over time.")

    para3 = " ".join(actions)

    return f"{para1} {para2} {para3}"


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

    # ── 1. Correlation insights (r > 0.3, BH-corrected p < 0.05) ─────────────
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
                "evidence": f"Isolation Forest, {len(numeric_cols)} features, {anomaly_count} anomalous rows",
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
            q1, q3 = float(col_data.quantile(0.25)), float(col_data.quantile(0.75))
            iqr = q3 - q1
            if iqr <= 0:
                continue
            lower, upper = q1 - 3.0 * iqr, q3 + 3.0 * iqr
            outlier_mask = (col_data < lower) | (col_data > upper)
            outlier_count = int(outlier_mask.sum())
            method_label, evidence_detail = "IQR (3× fence)", f"IQR fence [{lower:.3g}, {upper:.3g}], skew={skew:.2f}"
        else:
            if col_data.std() < 1e-10:
                continue  # constant column — zscore undefined
            z_scores = np.abs(stats.zscore(col_data))
            outlier_count = int((z_scores > 3).sum())
            worst_z = round(float(z_scores.max()), 1)
            method_label, evidence_detail = "Z-score (±3σ)", f"Max Z-score: {worst_z}. Mean: {col_data.mean():.2f}, Std: {col_data.std():.2f}"

        if outlier_count > 0:
            outlier_pct = round(outlier_count / len(col_data) * 100, 1)
            insights.append({
                "type": "anomaly",
                "severity": "high" if outlier_pct > 5 else "medium",
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

    # ── 4. Distribution skewness ──────────────────────────────────────────────
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
                    f"Consider log-transforming '{col}' before modeling. "
                    f"Gap between mean ({col_data.mean():.2f}) and median ({col_data.median():.2f}) confirms skew."
                ),
            })

    # ── 5. Segment gap analysis (Welch's t-test + Cohen's d) ─────────────────
    for cat_col in categorical_cols:
        for num_col in numeric_cols:
            group_data = {
                name: grp.dropna().values
                for name, grp in df.groupby(cat_col)[num_col]
            }
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
            _, welch_p = stats.ttest_ind(valid_groups[max_group], valid_groups[min_group], equal_var=False)
            if welch_p >= 0.05:
                continue
            d = _cohens_d(valid_groups[max_group], valid_groups[min_group])
            effect_label = "large" if abs(d) >= 0.8 else "medium" if abs(d) >= 0.5 else "small"
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
                    f"it significantly outperforms '{min_group}' on {num_col} with a {effect_label} effect size."
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
            group_sizes = df.groupby(cat_col)[target_col].count()
            large_groups = group_sizes[group_sizes >= 20].index
            rates = df[df[cat_col].isin(large_groups)].groupby(cat_col)[target_col].apply(
                lambda x: (x == vals[0]).mean()
            ).dropna()
            if len(rates) < 2:
                continue
            max_group, min_group = rates.idxmax(), rates.idxmin()
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

    # ── 7. High-cardinality columns ───────────────────────────────────────────
    for col in df.select_dtypes(include=["object", "category"]).columns:
        n_unique, n_rows = df[col].nunique(), len(df)
        ratio = n_unique / n_rows
        if ratio > 0.8 and n_unique > 50:
            insights.append({
                "type": "data_quality",
                "severity": "low",
                "confidence": 90.0,
                "title": f"High-cardinality column: {col}",
                "finding": f"'{col}' has {n_unique} unique values ({ratio:.0%} of rows). May be an identifier or free-text field.",
                "evidence": f"{n_unique} unique values out of {n_rows} rows",
                "action": f"Consider whether '{col}' should be excluded from analysis or bucketed/encoded.",
            })

    # ── 8. Missing data patterns ──────────────────────────────────────────────
    missing = df.isnull().sum()
    for col, count in missing[missing > 0].items():
        pct = round(count / len(df) * 100, 1)
        if pct > 5:
            insights.append({
                "type": "data_quality",
                "severity": "high" if pct > 30 else "medium",
                "confidence": 99.0,
                "title": f"Missing data in {col}",
                "finding": f"{count} records ({pct}% of data) are missing values in '{col}'.",
                "evidence": f"{count}/{len(df)} rows missing ({pct}%)",
                "action": (
                    f"{'Drop this column or impute carefully.' if pct > 40 else 'Impute with median/mode or model-based imputation.'}"
                ),
            })

    # ── 9. Constant columns ───────────────────────────────────────────────────
    for col in numeric_cols:
        col_data = df[col].dropna()
        if len(col_data) < 5 or col_data.std() >= 1e-6:
            continue
        insights.append({
            "type": "data_quality",
            "severity": "medium",
            "confidence": 100.0,
            "title": f"Constant column: {col}",
            "finding": f"'{col}' has zero variance — all values are identical ({col_data.iloc[0]}).",
            "evidence": f"Std={col_data.std():.2e}, unique values={col_data.nunique()}",
            "action": f"Remove '{col}' from any model or analysis — it carries no information.",
        })

    # ── 10. Advanced insights ─────────────────────────────────────────────────
    insights += _concentration_risk(df, numeric_cols, categorical_cols)
    insights += _interaction_effects(df, numeric_cols, categorical_cols)
    insights += _simpsons_paradox_hints(df, numeric_cols, categorical_cols)
    insights += _missing_data_patterns(df, numeric_cols)
    insights += _leading_indicators(df, numeric_cols)
    insights += _trend_analysis(df, numeric_cols)
    insights += _multicollinearity(df, numeric_cols)

    # Sort and deduplicate
    severity_order = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda x: (severity_order.get(x.get("severity", "low"), 2), -x["confidence"]))

    # Deduplicate: skip insights with very similar titles
    seen_titles = set()
    deduped = []
    for insight in insights:
        title_key = insight["title"][:40].lower()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            deduped.append(insight)

    top_insights = deduped[:15]

    # ── 11. Narrative executive summary ──────────────────────────────────────
    narrative = _generate_narrative(top_insights, df)

    return top_insights, narrative


def get_dataset_summary(df: pd.DataFrame) -> dict:
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "numeric_cols": len(df.select_dtypes(include=[np.number]).columns),
        "categorical_cols": len(df.select_dtypes(include=["object"]).columns),
        "datetime_cols": len(df.select_dtypes(include=["datetime64"]).columns),
        "missing_pct": round(df.isnull().sum().sum() / max(len(df) * len(df.columns), 1) * 100, 1),
    }

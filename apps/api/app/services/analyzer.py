import pandas as pd
import numpy as np
from scipy import stats
from itertools import combinations

def analyze_dataset(df):
    insights = []

    # Exclude ID-like columns
    id_cols = [col for col in df.columns if 'id' in col.lower()]
    df = df.drop(columns=id_cols, errors='ignore')

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = [
        col for col in df.select_dtypes(include=['object', 'category']).columns
        if df[col].nunique() < 20
    ]

    # 1. Correlation insights
    if len(numeric_cols) >= 2:
        for col1, col2 in combinations(numeric_cols, 2):
            clean = df[[col1, col2]].dropna()
            if len(clean) < 10:
                continue
            corr, pvalue = stats.pearsonr(clean[col1], clean[col2])
            if abs(corr) > 0.5 and pvalue < 0.05:
                direction = "positively" if corr > 0 else "negatively"
                strength = "strongly" if abs(corr) > 0.8 else "moderately"
                insights.append({
                    "type": "correlation",
                    "confidence": round(abs(corr) * 100, 1),
                    "title": f"Hidden relationship: {col1} and {col2}",
                    "finding": f"{col1} and {col2} are {strength} {direction} correlated (r={corr:.2f}). When {col1} increases, {col2} tends to {'increase' if corr > 0 else 'decrease'}.",
                    "action": f"Investigate whether {col1} is driving {col2} — this relationship could be exploited strategically."
                })

    # 2. Anomaly detection
    for col in numeric_cols:
        col_data = df[col].dropna()
        if len(col_data) < 10:
            continue
        z_scores = np.abs(stats.zscore(col_data))
        outlier_count = (z_scores > 3).sum()
        if outlier_count > 0:
            outlier_pct = round(outlier_count / len(col_data) * 100, 1)
            insights.append({
                "type": "anomaly",
                "confidence": round(min(95, 70 + outlier_pct * 2), 1),
                "title": f"Anomalies detected in {col}",
                "finding": f"{outlier_count} records ({outlier_pct}% of data) in {col} are statistical outliers — more than 3 standard deviations from the mean.",
                "action": f"Review these {outlier_count} records in {col}. They could represent errors, fraud, or your most extreme customers."
            })

    # 3. Categorical vs numeric — churn rate style analysis
    for cat_col in categorical_cols:
        for num_col in numeric_cols:
            groups = df.groupby(cat_col)[num_col].mean().dropna()
            if len(groups) < 2:
                continue
            max_group = groups.idxmax()
            min_group = groups.idxmin()
            if groups[min_group] == 0:
                continue
            ratio = groups[max_group] / groups[min_group]
            if ratio > 1.5:
                insights.append({
                    "type": "segment",
                    "confidence": round(min(95, 55 + ratio * 4), 1),
                    "title": f"Segment gap: {cat_col} vs {num_col}",
                    "finding": f"'{max_group}' has {ratio:.1f}x higher average {num_col} than '{min_group}' ({groups[max_group]:.2f} vs {groups[min_group]:.2f}).",
                    "action": f"Prioritize segments like '{max_group}' — they significantly outperform '{min_group}' on {num_col}."
                })

    # 4. Binary categorical churn-style rates
    binary_cols = [col for col in categorical_cols if df[col].nunique() == 2]
    for target_col in binary_cols:
        vals = df[target_col].unique()
        for cat_col in categorical_cols:
            if cat_col == target_col:
                continue
            rates = df.groupby(cat_col)[target_col].apply(
                lambda x: (x == vals[0]).mean()
            ).dropna()
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
                    "confidence": round(min(95, 55 + ratio * 5), 1),
                    "title": f"Rate gap: {cat_col} vs {target_col}",
                    "finding": f"'{max_group}' has {ratio:.1f}x higher '{vals[0]}' rate than '{min_group}' ({rates[max_group]:.1%} vs {rates[min_group]:.1%}).",
                    "action": f"Segment '{max_group}' shows dramatically different {target_col} behavior — worth targeting separately."
                })

    # 5. Missing data patterns
    missing = df.isnull().sum()
    for col, count in missing[missing > 0].items():
        pct = round(count / len(df) * 100, 1)
        if pct > 5:
            insights.append({
                "type": "data_quality",
                "confidence": 99.0,
                "title": f"Data gap in {col}",
                "finding": f"{count} records ({pct}% of data) are missing values in {col}.",
                "action": f"Investigate why {col} is missing for {pct}% of records — this could be hiding a pattern."
            })

    # Sort by confidence and return top 10
    insights.sort(key=lambda x: x["confidence"], reverse=True)
    return insights[:10]


def get_dataset_summary(df):
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "numeric_cols": len(df.select_dtypes(include=[np.number]).columns),
        "categorical_cols": len(df.select_dtypes(include=['object']).columns),
        "missing_pct": round(df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100, 1)
    }
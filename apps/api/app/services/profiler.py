import pandas as pd
import numpy as np
from scipy import stats

def profile_dataset(df):
    profile = []
    
    for col in df.columns:
        col_data = df[col]
        missing = col_data.isnull().sum()
        missing_pct = round(missing / len(df) * 100, 1)
        unique = col_data.nunique()
        unique_pct = round(unique / len(df) * 100, 1)
        dtype = str(col_data.dtype)

        col_profile = {
            "column": col,
            "dtype": dtype,
            "missing": missing,
            "missing_pct": missing_pct,
            "unique": unique,
            "unique_pct": unique_pct,
        }

        if col_data.dtype in [np.float64, np.int64, float, int]:
            clean = col_data.dropna()
            col_profile.update({
                "type": "numeric",
                "mean": round(float(clean.mean()), 2),
                "median": round(float(clean.median()), 2),
                "std": round(float(clean.std()), 2),
                "min": round(float(clean.min()), 2),
                "max": round(float(clean.max()), 2),
                "q25": round(float(clean.quantile(0.25)), 2),
                "q75": round(float(clean.quantile(0.75)), 2),
                "skewness": round(float(clean.skew()), 2),
                "outliers": int((np.abs(stats.zscore(clean)) > 3).sum()),
                "zeros": int((clean == 0).sum()),
            })
        elif col_data.dtype == 'datetime64[ns]':
            clean = col_data.dropna()
            col_profile.update({
                "type": "datetime",
                "min": str(clean.min()),
                "max": str(clean.max()),
                "range_days": (clean.max() - clean.min()).days,
            })
        else:
            top_values = col_data.value_counts().head(5).to_dict()
            col_profile.update({
                "type": "categorical",
                "top_values": top_values,
                "most_common": str(col_data.mode()[0]) if len(col_data.mode()) > 0 else "N/A",
                "most_common_pct": round(col_data.value_counts().iloc[0] / len(df) * 100, 1) if len(col_data.value_counts()) > 0 else 0,
            })

        # Data quality flags
        flags = []
        if missing_pct > 30:
            flags.append("high missing data")
        if unique_pct == 100 and col_data.dtype == object:
            flags.append("possible ID column")
        if col_data.dtype in [np.float64, np.int64] and col_profile.get("outliers", 0) > 0:
            flags.append(f"{col_profile['outliers']} outliers")
        if col_data.dtype in [np.float64, np.int64] and abs(col_profile.get("skewness", 0)) > 2:
            flags.append("highly skewed")
        if unique == 1:
            flags.append("constant column")

        col_profile["flags"] = flags
        profile.append(col_profile)

    return profile

def calculate_health_score(df):
    scores = {}
    deductions = []

    # 1. Completeness (30 points)
    missing_pct = df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100
    completeness = max(0, 30 - missing_pct * 2)
    scores["completeness"] = round(completeness, 1)
    if missing_pct > 0:
        deductions.append(f"Missing data: -{round(missing_pct * 2, 1)} pts ({missing_pct:.1f}% of values missing)")

    # 2. Uniqueness (20 points)
    dupe_pct = df.duplicated().sum() / len(df) * 100
    uniqueness = max(0, 20 - dupe_pct * 2)
    scores["uniqueness"] = round(uniqueness, 1)
    if dupe_pct > 0:
        deductions.append(f"Duplicate rows: -{round(dupe_pct * 2, 1)} pts ({dupe_pct:.1f}% duplicates)")

    # 3. Consistency (20 points)
    consistency = 20
    for col in df.select_dtypes(include='object').columns:
        if df[col].str.strip().ne(df[col]).any():
            consistency -= 2
            deductions.append(f"Whitespace in '{col}': -2 pts")
            break
    mixed_type_cols = 0
    for col in df.columns:
        if df[col].dtype == object:
            numeric_ratio = pd.to_numeric(df[col], errors='coerce').notna().mean()
            if 0.1 < numeric_ratio < 0.9:
                mixed_type_cols += 1
    if mixed_type_cols > 0:
        deduction = min(10, mixed_type_cols * 3)
        consistency -= deduction
        deductions.append(f"Mixed data types in {mixed_type_cols} columns: -{deduction} pts")
    scores["consistency"] = round(max(0, consistency), 1)

    # 4. Validity (15 points)
    validity = 15
    numeric_cols = df.select_dtypes(include='number').columns
    outlier_cols = 0
    for col in numeric_cols:
        from scipy import stats
        z = np.abs(stats.zscore(df[col].dropna()))
        if (z > 3).sum() > 0:
            outlier_cols += 1
    if outlier_cols > 0:
        deduction = min(10, outlier_cols * 2)
        validity -= deduction
        deductions.append(f"Outliers in {outlier_cols} columns: -{deduction} pts")
    scores["validity"] = round(max(0, validity), 1)

    # 5. Structure (15 points)
    structure = 15
    id_like_cols = [col for col in df.columns if 'id' in col.lower() and df[col].nunique() == len(df)]
    constant_cols = [col for col in df.columns if df[col].nunique() == 1]
    if constant_cols:
        deduction = min(8, len(constant_cols) * 2)
        structure -= deduction
        deductions.append(f"Constant columns: -{deduction} pts ({len(constant_cols)} columns with 1 unique value)")
    scores["structure"] = round(max(0, structure), 1)

    total = sum(scores.values())
    
    if total >= 85:
        grade = "A"
        label = "Excellent"
        color = "#68d391"
    elif total >= 70:
        grade = "B"
        label = "Good"
        color = "#90cdf4"
    elif total >= 55:
        grade = "C"
        label = "Fair"
        color = "#f6ad55"
    elif total >= 40:
        grade = "D"
        label = "Poor"
        color = "#fc8181"
    else:
        grade = "F"
        label = "Critical"
        color = "#e53e3e"

    return {
        "total": round(total, 1),
        "grade": grade,
        "label": label,
        "color": color,
        "breakdown": scores,
        "deductions": deductions,
        "max_scores": {
            "completeness": 30,
            "uniqueness": 20,
            "consistency": 20,
            "validity": 15,
            "structure": 15
        }
    }
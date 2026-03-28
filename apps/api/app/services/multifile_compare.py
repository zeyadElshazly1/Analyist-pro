import pandas as pd
import numpy as np
from app.services.file_loader import load_dataset
from app.services.cleaner import clean_dataset
from app.services.profiler import calculate_health_score


def compare_files(path_a: str, path_b: str, label_a: str = "File A", label_b: str = "File B") -> dict:
    # Load and clean both files
    df_a_raw = load_dataset(path_a)
    df_b_raw = load_dataset(path_b)
    df_a, _, _ = clean_dataset(df_a_raw)
    df_b, _, _ = clean_dataset(df_b_raw)

    cols_a = set(df_a.columns.tolist())
    cols_b = set(df_b.columns.tolist())
    shared = sorted(cols_a & cols_b)
    only_a = sorted(cols_a - cols_b)
    only_b = sorted(cols_b - cols_a)

    # Health scores
    score_a = calculate_health_score(df_a)
    score_b = calculate_health_score(df_b)

    # Numeric stats comparison on shared columns
    numeric_shared = [
        col for col in shared
        if pd.api.types.is_numeric_dtype(df_a[col]) and pd.api.types.is_numeric_dtype(df_b[col])
    ]
    stats_table = []
    for col in numeric_shared[:15]:
        a_vals = df_a[col].dropna()
        b_vals = df_b[col].dropna()
        stats_table.append({
            "column": col,
            "a_mean": round(float(a_vals.mean()), 4) if len(a_vals) > 0 else None,
            "b_mean": round(float(b_vals.mean()), 4) if len(b_vals) > 0 else None,
            "a_std": round(float(a_vals.std()), 4) if len(a_vals) > 1 else None,
            "b_std": round(float(b_vals.std()), 4) if len(b_vals) > 1 else None,
            "a_median": round(float(a_vals.median()), 4) if len(a_vals) > 0 else None,
            "b_median": round(float(b_vals.median()), 4) if len(b_vals) > 0 else None,
            "mean_diff_pct": (
                round((float(b_vals.mean()) - float(a_vals.mean())) / abs(float(a_vals.mean())) * 100, 2)
                if len(a_vals) > 0 and len(b_vals) > 0 and float(a_vals.mean()) != 0
                else None
            ),
        })

    # Overlay histograms for top 3 shared numeric columns
    histograms = []
    for col in numeric_shared[:3]:
        a_vals = df_a[col].dropna()
        b_vals = df_b[col].dropna()
        combined_min = min(float(a_vals.min()), float(b_vals.min()))
        combined_max = max(float(a_vals.max()), float(b_vals.max()))
        bins = np.linspace(combined_min, combined_max, 12)
        a_counts, _ = np.histogram(a_vals, bins=bins)
        b_counts, _ = np.histogram(b_vals, bins=bins)
        hist_data = []
        for i in range(len(a_counts)):
            hist_data.append({
                "label": f"{bins[i]:.3g}–{bins[i+1]:.3g}",
                "a_count": int(a_counts[i]),
                "b_count": int(b_counts[i]),
            })
        histograms.append({"column": col, "bins": hist_data})

    # Row overlap estimate (hash-based on shared cols)
    overlap_count = 0
    overlap_pct = None
    if shared:
        try:
            hash_a = set(df_a[shared].apply(lambda r: hash(tuple(r)), axis=1))
            hash_b = set(df_b[shared].apply(lambda r: hash(tuple(r)), axis=1))
            overlap_count = len(hash_a & hash_b)
            overlap_pct = round(overlap_count / max(len(hash_a), 1) * 100, 2)
        except Exception:
            pass

    return {
        "label_a": label_a,
        "label_b": label_b,
        "rows": {"a": len(df_a), "b": len(df_b), "diff": len(df_b) - len(df_a)},
        "columns": {"a": len(df_a.columns), "b": len(df_b.columns)},
        "schema": {
            "shared": shared,
            "only_a": only_a,
            "only_b": only_b,
            "shared_count": len(shared),
        },
        "health_scores": {
            "a": {"total": score_a["total"], "grade": score_a["grade"], "label": score_a["label"]},
            "b": {"total": score_b["total"], "grade": score_b["grade"], "label": score_b["label"]},
        },
        "stats_comparison": stats_table,
        "histograms": histograms,
        "row_overlap": {
            "count": overlap_count,
            "pct_of_a": overlap_pct,
        },
    }

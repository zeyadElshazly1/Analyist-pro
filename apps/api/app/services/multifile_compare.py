import pandas as pd
import numpy as np
from app.services.file_loader import load_dataset
from app.services.cleaner import clean_dataset
from app.services.profiler import calculate_health_score


def compare_files(path_a: str, path_b: str) -> dict:
    df_a, _, _ = clean_dataset(load_dataset(path_a))
    df_b, _, _ = clean_dataset(load_dataset(path_b))

    cols_a = set(df_a.columns)
    cols_b = set(df_b.columns)
    shared = cols_a & cols_b

    health_a = calculate_health_score(df_a)
    health_b = calculate_health_score(df_b)

    shared_numeric = [
        c for c in shared
        if pd.api.types.is_numeric_dtype(df_a[c]) and pd.api.types.is_numeric_dtype(df_b[c])
    ]

    column_comparison = []
    for col in shared_numeric:
        column_comparison.append({
            "column": col,
            "file_a": {
                "mean": round(float(df_a[col].mean()), 3),
                "median": round(float(df_a[col].median()), 3),
                "std": round(float(df_a[col].std()), 3),
                "min": round(float(df_a[col].min()), 3),
                "max": round(float(df_a[col].max()), 3),
            },
            "file_b": {
                "mean": round(float(df_b[col].mean()), 3),
                "median": round(float(df_b[col].median()), 3),
                "std": round(float(df_b[col].std()), 3),
                "min": round(float(df_b[col].min()), 3),
                "max": round(float(df_b[col].max()), 3),
            },
        })

    histograms = {}
    for col in shared_numeric[:3]:
        all_vals = list(df_a[col].dropna()) + list(df_b[col].dropna())
        bins = np.linspace(min(all_vals), max(all_vals), 11)
        hist_a, _ = np.histogram(df_a[col].dropna(), bins=bins)
        hist_b, _ = np.histogram(df_b[col].dropna(), bins=bins)
        histograms[col] = [
            {"label": f"{bins[i]:.1f}–{bins[i+1]:.1f}", "file_a": int(hist_a[i]), "file_b": int(hist_b[i])}
            for i in range(len(hist_a))
        ]

    row_overlap = None
    if shared:
        try:
            row_overlap = len(pd.merge(df_a[list(shared)], df_b[list(shared)], how="inner"))
        except Exception:
            pass

    return {
        "file_a": {"rows": len(df_a), "columns": len(df_a.columns), "health_score": health_a["total"], "health_grade": health_a["grade"]},
        "file_b": {"rows": len(df_b), "columns": len(df_b.columns), "health_score": health_b["total"], "health_grade": health_b["grade"]},
        "schema": {
            "shared_columns": sorted(list(shared)),
            "only_in_a": sorted(list(cols_a - cols_b)),
            "only_in_b": sorted(list(cols_b - cols_a)),
        },
        "column_comparison": column_comparison,
        "histograms": histograms,
        "row_overlap": row_overlap,
    }

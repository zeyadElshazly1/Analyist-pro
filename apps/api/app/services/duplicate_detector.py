import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors


def detect_duplicates(df: pd.DataFrame) -> dict:
    exact_mask = df.duplicated(keep=False)
    exact_count = int(df.duplicated().sum())
    exact_pct = round(exact_count / len(df) * 100, 2)
    exact_rows = df[exact_mask].head(20).to_dict(orient="records")

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    near_count = 0
    near_rows = []

    if len(numeric_cols) >= 1 and len(df) >= 2:
        try:
            X = df[numeric_cols].dropna()
            if len(X) >= 2:
                X_scaled = StandardScaler().fit_transform(X)
                k = min(2, len(X) - 1)
                knn = NearestNeighbors(n_neighbors=k + 1, metric="euclidean")
                knn.fit(X_scaled)
                distances, _ = knn.kneighbors(X_scaled)
                mask = distances[:, 1] < 0.1
                near_count = int(mask.sum())
                near_indices = X.index[mask].tolist()
                near_rows = [
                    {**df.loc[idx].to_dict(), "_nn_distance": round(float(distances[i, 1]), 4)}
                    for i, idx in enumerate(near_indices[:10])
                ]
        except Exception:
            pass

    return {
        "total_rows": len(df),
        "exact_duplicates": {
            "count": exact_count,
            "pct": exact_pct,
            "sample_rows": exact_rows,
        },
        "near_duplicates": {
            "count": near_count,
            "threshold": 0.1,
            "numeric_cols_used": numeric_cols,
            "sample_rows": near_rows,
        },
    }

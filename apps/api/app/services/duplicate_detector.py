import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors


def detect_duplicates(df: pd.DataFrame) -> dict:
    # 1. Exact duplicates
    exact_mask = df.duplicated(keep=False)
    exact_count = int(df.duplicated().sum())
    exact_pct = round(exact_count / max(len(df), 1) * 100, 2)

    exact_sample = []
    if exact_count > 0:
        duped_rows = df[exact_mask].head(20)
        for _, row in duped_rows.iterrows():
            exact_sample.append({k: (v if pd.notna(v) else None) for k, v in row.to_dict().items()})

    # Group exact duplicates
    exact_groups = []
    if exact_count > 0:
        groups = df[exact_mask].groupby(df[exact_mask].columns.tolist(), dropna=False)
        for _key, group in list(groups)[:10]:
            exact_groups.append({
                "indices": group.index.tolist(),
                "count": len(group),
            })

    # 2. Near-duplicates via KNN on numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    near_duplicate_rows = []
    near_count = 0
    near_groups = []

    if len(numeric_cols) >= 2:
        numeric_data = df[numeric_cols].dropna()
        if len(numeric_data) >= 5:
            try:
                scaler = StandardScaler()
                scaled = scaler.fit_transform(numeric_data)
                # Adaptive threshold based on dimensionality
                n_features = len(numeric_cols)
                threshold = 0.1 * np.sqrt(n_features)
                nbrs = NearestNeighbors(n_neighbors=min(3, len(numeric_data) - 1), algorithm="auto")
                nbrs.fit(scaled)
                distances, indices = nbrs.kneighbors(scaled)

                seen = set()
                for i, (dists, nbr_idxs) in enumerate(zip(distances, indices)):
                    for dist, nbr_idx in zip(dists[1:], nbr_idxs[1:]):
                        if dist < threshold and i not in seen and nbr_idx not in seen:
                            orig_i = numeric_data.index[i]
                            orig_j = numeric_data.index[nbr_idx]
                            near_groups.append({
                                "indices": [int(orig_i), int(orig_j)],
                                "distance": round(float(dist), 4),
                            })
                            seen.add(i)
                            near_count += 1

                # Collect near-duplicate rows for display
                near_indices = set()
                for g in near_groups[:20]:
                    near_indices.update(g["indices"])
                for idx in list(near_indices)[:20]:
                    try:
                        row = df.loc[idx].to_dict()
                        near_duplicate_rows.append({"index": int(idx), **{k: (v if pd.notna(v) else None) for k, v in row.items()}})
                    except Exception:
                        pass
            except Exception:
                pass

    total_affected = exact_count + near_count
    impact_pct = round(total_affected / max(len(df), 1) * 100, 2)

    return {
        "total_rows": len(df),
        "exact": {
            "count": exact_count,
            "pct": exact_pct,
            "sample_rows": exact_sample[:10],
            "groups": exact_groups,
        },
        "near_duplicates": {
            "count": near_count,
            "groups": near_groups[:20],
            "sample_rows": near_duplicate_rows[:10],
        },
        "impact": {
            "total_affected": total_affected,
            "impact_pct": impact_pct,
            "recommendation": (
                "Consider removing exact duplicates before analysis."
                if exact_count > 0
                else "No exact duplicates found. Review near-duplicates manually."
            ),
        },
    }

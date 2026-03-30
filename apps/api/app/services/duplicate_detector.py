import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors


def _explain_pair(df: pd.DataFrame, idx_a: int, idx_b: int) -> list[dict]:
    """Return a per-column diff for two rows, highlighting what differs."""
    try:
        row_a = df.loc[idx_a]
        row_b = df.loc[idx_b]
    except KeyError:
        return []
    diffs = []
    for col in df.columns:
        va = row_a[col]
        vb = row_b[col]
        if pd.isna(va) and pd.isna(vb):
            continue
        if pd.isna(va) or pd.isna(vb):
            diffs.append({
                "column": col,
                "value_a": None if pd.isna(va) else va,
                "value_b": None if pd.isna(vb) else vb,
                "diff_type": "one_missing",
            })
            continue
        if va != vb:
            diff_info: dict = {"column": col, "value_a": va, "value_b": vb}
            if pd.api.types.is_numeric_dtype(df[col]):
                try:
                    pct = abs(float(va) - float(vb)) / (abs(float(va)) + 1e-10) * 100
                    diff_info["pct_diff"] = round(pct, 1)
                    diff_info["diff_type"] = "numeric"
                except Exception:
                    diff_info["diff_type"] = "value"
            else:
                diff_info["diff_type"] = "text"
            diffs.append(diff_info)
    return diffs


def _detect_composite_key(df: pd.DataFrame) -> list[str] | None:
    """
    Find the minimal set of columns that uniquely identifies each row.
    Returns column names of the natural key, or None if none found.
    """
    # First try: single columns
    for col in df.columns:
        if df[col].nunique() == len(df) and df[col].notna().all():
            return [col]

    # Try pairs (limited to first 10 columns for performance)
    candidates = df.columns[:10].tolist()
    for i, c1 in enumerate(candidates):
        for c2 in candidates[i + 1:]:
            combo = df[[c1, c2]].dropna()
            if len(combo) == len(df) and combo.duplicated().sum() == 0:
                return [c1, c2]

    return None


def _fuzzy_text_groups(series: pd.Series, threshold: float = 85.0) -> list[dict]:
    """
    Detect near-duplicate text values using fuzzy string matching.
    Returns groups of similar values.
    Requires rapidfuzz (optional — silently skips if not installed).
    """
    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        return []

    values = series.dropna().astype(str).unique().tolist()
    if len(values) > 500:
        values = values[:500]  # cap for performance

    groups = []
    seen = set()
    for val in values:
        if val in seen:
            continue
        matches = process.extract(val, values, scorer=fuzz.token_sort_ratio, limit=20)
        similar = [m[0] for m in matches if m[1] >= threshold and m[0] != val]
        if similar:
            group_vals = [val] + [s for s in similar if s not in seen]
            if len(group_vals) > 1:
                groups.append({
                    "canonical": val,
                    "similar_values": group_vals[1:],
                    "count": len(group_vals),
                    "sample_score": next(
                        (round(m[1], 1) for m in matches if m[0] == group_vals[1]),
                        None,
                    ),
                })
                seen.update(group_vals)
    return groups[:20]


def detect_duplicates(df: pd.DataFrame) -> dict:
    # ── 1. Exact duplicates ───────────────────────────────────────────────────
    exact_mask = df.duplicated(keep=False)
    exact_count = int(df.duplicated().sum())
    exact_pct = round(exact_count / max(len(df), 1) * 100, 2)

    exact_sample = []
    if exact_count > 0:
        duped_rows = df[exact_mask].head(20)
        for _, row in duped_rows.iterrows():
            exact_sample.append({k: (v if pd.notna(v) else None) for k, v in row.to_dict().items()})

    exact_groups = []
    if exact_count > 0:
        try:
            # Convert all columns to string before groupby to avoid unhashable type errors
            df_str = df[exact_mask].astype(str)
            groups = df_str.groupby(df_str.columns.tolist(), dropna=False)
            for _key, group in list(groups)[:10]:
                exact_groups.append({
                    "indices": group.index.tolist(),
                    "count": len(group),
                })
        except Exception:
            # Fallback: just report duplicated rows without grouping
            pass

    # ── 2. Near-duplicates via adaptive-threshold KNN ────────────────────────
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

                # Adaptive threshold: 5th percentile of all pairwise neighbor distances
                n_neighbors_fit = min(10, len(numeric_data) - 1)
                nbrs = NearestNeighbors(n_neighbors=n_neighbors_fit, algorithm="auto")
                nbrs.fit(scaled)
                all_distances, all_indices = nbrs.kneighbors(scaled)
                # Use the 1st neighbor distances (closest non-self) to set threshold
                nearest_dists = all_distances[:, 1]  # skip self at index 0
                threshold = float(np.percentile(nearest_dists, 5))
                threshold = max(threshold, 0.05)  # floor to avoid trivial matches

                seen = set()
                for i, (dists, nbr_idxs) in enumerate(zip(all_distances, all_indices)):
                    for dist, nbr_idx in zip(dists[1:], nbr_idxs[1:]):
                        if dist <= threshold and i not in seen and nbr_idx not in seen:
                            orig_i = int(numeric_data.index[i])
                            orig_j = int(numeric_data.index[nbr_idx])
                            explanation = _explain_pair(df, orig_i, orig_j)
                            near_groups.append({
                                "indices": [orig_i, orig_j],
                                "distance": round(float(dist), 4),
                                "explanation": explanation,
                                "summary": (
                                    f"Rows {orig_i} and {orig_j} are {len([d for d in explanation if d['diff_type'] != 'value'])} "
                                    f"numeric columns apart with {len([d for d in explanation if d['diff_type'] in ('text', 'value')])} "
                                    f"text differences"
                                    if explanation else "Rows are numerically nearly identical"
                                ),
                            })
                            seen.add(i)
                            near_count += 1

                near_indices = set()
                for g in near_groups[:20]:
                    near_indices.update(g["indices"])
                for idx in list(near_indices)[:20]:
                    try:
                        row = df.loc[idx].to_dict()
                        near_duplicate_rows.append({
                            "index": int(idx),
                            **{k: (v if pd.notna(v) else None) for k, v in row.items()}
                        })
                    except Exception:
                        pass
            except Exception:
                pass

    # ── 3. Composite key detection ───────────────────────────────────────────
    composite_key = _detect_composite_key(df)

    # ── 4. Fuzzy text matching on string columns ─────────────────────────────
    fuzzy_matches: dict[str, list] = {}
    text_cols = df.select_dtypes(include=["object"]).columns.tolist()
    for col in text_cols[:3]:
        groups_found = _fuzzy_text_groups(df[col])
        if groups_found:
            fuzzy_matches[col] = groups_found

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
            "adaptive_threshold_used": True,
        },
        "fuzzy_text": fuzzy_matches,
        "composite_key": {
            "columns": composite_key,
            "found": composite_key is not None,
            "note": (
                f"Natural primary key identified: {composite_key}"
                if composite_key else "No unique identifier column(s) found — dataset may allow duplicate records by design"
            ),
        },
        "impact": {
            "total_affected": total_affected,
            "impact_pct": impact_pct,
            "recommendation": (
                "Remove exact duplicates before analysis — they inflate counts and distort averages."
                if exact_count > 0
                else "No exact duplicates found. Review near-duplicates and fuzzy text matches manually."
            ),
        },
    }

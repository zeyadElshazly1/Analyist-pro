import pandas as pd
import numpy as np


def build_chart_data(df: pd.DataFrame):
    charts = []
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = [
        col for col in df.select_dtypes(exclude=["number"]).columns
        if df[col].nunique() <= 20
    ]
    date_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()

    # 1. Distribution histogram for first 2 numeric columns
    for col in numeric_cols[:2]:
        series = df[col].dropna()
        if len(series) < 2:
            continue
        bins = pd.cut(series, bins=min(8, series.nunique()))
        counts = bins.value_counts().sort_index()
        charts.append({
            "chart_type": "bar",
            "title": f"Distribution of {col}",
            "x_key": "label",
            "y_key": "value",
            "data": [
                {"label": str(interval), "value": int(count)}
                for interval, count in counts.items()
            ],
        })

    # 2. Category breakdown for categorical columns
    for col in categorical_cols[:2]:
        counts = df[col].fillna("Missing").astype(str).value_counts().head(10)
        chart_type = "pie" if counts.shape[0] <= 6 else "bar"
        charts.append({
            "chart_type": chart_type,
            "title": f"Breakdown by {col}",
            "x_key": "label",
            "y_key": "value",
            "data": [
                {"label": str(label), "value": int(count)}
                for label, count in counts.items()
            ],
        })

    # 3. Scatter plot for first two numeric columns
    if len(numeric_cols) >= 2:
        col1, col2 = numeric_cols[0], numeric_cols[1]
        clean = df[[col1, col2]].dropna().head(300)
        if len(clean) >= 5:
            charts.append({
                "chart_type": "scatter",
                "title": f"{col1} vs {col2}",
                "x_key": col1,
                "y_key": col2,
                "data": clean.to_dict(orient="records"),
            })

    # 4. Time series if datetime column exists
    if date_cols and numeric_cols:
        date_col = date_cols[0]
        val_col = numeric_cols[0]
        ts = df[[date_col, val_col]].dropna().sort_values(date_col)
        if len(ts) >= 3:
            try:
                ts = ts.set_index(date_col).resample("ME")[val_col].mean().reset_index()
                ts.columns = ["date", "value"]
                ts["date"] = ts["date"].dt.strftime("%Y-%m")
                charts.append({
                    "chart_type": "line",
                    "title": f"{val_col} over time",
                    "x_key": "date",
                    "y_key": "value",
                    "data": [
                        {"date": str(row["date"]), "value": round(float(row["value"]), 2)}
                        for _, row in ts.iterrows()
                        if not pd.isna(row["value"])
                    ],
                })
            except Exception:
                pass

    if not charts:
        charts.append({
            "chart_type": "bar",
            "title": "No chartable data found",
            "x_key": "label",
            "y_key": "value",
            "data": [],
        })

    return charts

import pandas as pd


def build_chart_data(df: pd.DataFrame):
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(exclude=["number"]).columns.tolist()

    if numeric_cols:
        col = numeric_cols[0]
        series = df[col].dropna()

        if len(series) > 0:
            bins = pd.cut(series, bins=8)
            counts = bins.value_counts().sort_index()

            return {
                "chart_type": "bar",
                "title": f"Distribution of {col}",
                "x_key": "label",
                "y_key": "value",
                "data": [
                    {"label": str(interval), "value": int(count)}
                    for interval, count in counts.items()
                ],
            }

    if categorical_cols:
        col = categorical_cols[0]
        counts = df[col].fillna("Missing").astype(str).value_counts().head(10)

        return {
            "chart_type": "bar",
            "title": f"Top values in {col}",
            "x_key": "label",
            "y_key": "value",
            "data": [
                {"label": str(label), "value": int(count)}
                for label, count in counts.items()
            ],
        }

    return {
        "chart_type": "bar",
        "title": "No chartable data found",
        "x_key": "label",
        "y_key": "value",
        "data": [],
    }
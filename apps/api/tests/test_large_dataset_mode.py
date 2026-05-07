"""
Large dataset sampling for analysis / charts (Task 77C).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.analysis.domain.timeseries_finance import FINANCE_TS_PREMIUM_TITLE_ORDER
from app.services.analysis.large_dataset_mode import LARGE_DATASET_NARRATIVE_NOTE, prepare_analysis_frame
from app.services.analysis.orchestrator import analyze_dataset
from app.services.charting.budget import MAX_TIMESERIES_POINTS
from app.services.charting.orchestrator import build_chart_data


def _etf_base() -> pd.DataFrame:
    path = Path(__file__).resolve().parent / "fixtures" / "etf_prices_sample.csv"
    return pd.read_csv(path, parse_dates=["price_date"])


def _wide_financial_ts_rows(*, copies: int) -> pd.DataFrame:
    """Stack dated copies so row count scales without duplicate (symbol, date) keys."""
    base = _etf_base()
    parts: list[pd.DataFrame] = []
    for k in range(copies):
        d = base.copy()
        d["price_date"] = d["price_date"] + pd.Timedelta(days=400 * k)
        parts.append(d)
    return pd.concat(parts, ignore_index=True)


def test_large_financial_ts_triggers_mode_and_preserves_shape_meta(monkeypatch):
    import app.services.analysis.large_dataset_mode as ldm

    monkeypatch.setattr(ldm, "LARGE_DATASET_ROWS", 400)
    monkeypatch.setattr(ldm, "LARGE_DATASET_SAMPLE_ROWS", 150)

    big = _wide_financial_ts_rows(copies=4)
    assert len(big) > 400

    df_a, meta = prepare_analysis_frame(big)
    assert meta["large_dataset_mode"] is True
    assert meta["full_rows"] == len(big)
    assert meta["analyzed_rows"] == len(df_a)
    assert meta["full_rows"] > meta["analyzed_rows"]
    assert meta["sample_strategy"] == "timeseries_recent_rows_per_symbol"
    assert meta["symbol_count"] == big["fund_symbol"].nunique()


def test_large_financial_ts_insights_and_narrative(monkeypatch):
    import app.services.analysis.large_dataset_mode as ldm

    monkeypatch.setattr(ldm, "LARGE_DATASET_ROWS", 400)
    monkeypatch.setattr(ldm, "LARGE_DATASET_SAMPLE_ROWS", 200)

    big = _wide_financial_ts_rows(copies=4)
    df_a, meta = prepare_analysis_frame(big)
    insights, narrative = analyze_dataset(df_a)
    assert meta["large_dataset_mode"] is True
    full_story = narrative + LARGE_DATASET_NARRATIVE_NOTE
    assert "Large dataset mode used" in full_story
    titles = [str(i.get("title", "")) for i in insights]
    core_finance_titles = {
        "Top performers by total return",
        "Worst performers by total return",
        "Highest volatility symbols",
        "Largest drawdowns",
        "Highest volume symbols",
    }
    assert core_finance_titles.issubset(set(titles))
    assert len([t for t in FINANCE_TS_PREMIUM_TITLE_ORDER if t in titles]) >= 5


def test_finance_line_chart_payload_capped(monkeypatch):
    import app.services.analysis.large_dataset_mode as ldm

    monkeypatch.setattr(ldm, "LARGE_DATASET_ROWS", 400)
    monkeypatch.setattr(ldm, "LARGE_DATASET_SAMPLE_ROWS", 250)

    big = _wide_financial_ts_rows(copies=5)
    df_a, meta = prepare_analysis_frame(big)
    assert meta["large_dataset_mode"] is True
    charts = build_chart_data(df_a)
    price_chart = next(c for c in charts if c.get("title") == "Price trend by symbol")
    assert len(price_chart["data"]) <= MAX_TIMESERIES_POINTS


def test_small_financial_ts_unchanged(monkeypatch):
    import app.services.analysis.large_dataset_mode as ldm

    monkeypatch.setattr(ldm, "LARGE_DATASET_ROWS", 400)
    df = _etf_base()
    df_a, meta = prepare_analysis_frame(df)
    assert meta["large_dataset_mode"] is False
    assert meta["analyzed_rows"] == len(df)
    assert meta["sample_strategy"] == "full"


def test_large_generic_uses_uniform_sample(monkeypatch):
    import app.services.analysis.large_dataset_mode as ldm

    monkeypatch.setattr(ldm, "LARGE_DATASET_ROWS", 80)
    monkeypatch.setattr(ldm, "LARGE_DATASET_SAMPLE_ROWS", 40)

    df = pd.DataFrame({"x": range(120), "y": range(120)})
    df_a, meta = prepare_analysis_frame(df)
    assert meta["large_dataset_mode"] is True
    assert meta["sample_strategy"] == "random_uniform"
    assert len(df_a) == 40

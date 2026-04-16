"""
Robust anomaly detection using Median Absolute Deviation (MAD).

detect_anomalies(residuals) → list[bool]

Applied to STL residuals (trend + seasonality removed) rather than raw
linear-fit residuals, so the detection is not biased by outliers in the fit.
The 1.4826 constant scales MAD to match σ for a Gaussian distribution.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def detect_anomalies(residuals: pd.Series) -> list[bool]:
    med = float(residuals.median())
    mad = float((residuals - med).abs().median())

    if mad < 1e-10:
        std = float(residuals.std())
        if std < 1e-10:
            return [False] * len(residuals)
        z = np.abs(residuals - float(residuals.mean())) / std
        return (z > 2.5).tolist()

    robust_z = np.abs(residuals - med) / (1.4826 * mad)
    return (robust_z > 3.0).tolist()

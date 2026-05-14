"""
90O — Shadow activation gate.

Pure utility: inspects a profile_hygiene_shadow_meta dict and returns a
structured verdict on whether it is safe to activate profile hygiene.
No I/O, no side effects, no pipeline imports — stdlib only.
"""
from __future__ import annotations

from typing import Any


def evaluate_shadow_gate(
    shadow_meta: dict[str, Any],
    max_penalized_fraction: float = 0.50,
    max_abs_delta: float = 60.0,
) -> dict[str, Any]:
    """Return an activation safety verdict for a shadow meta dict.

    Parameters
    ----------
    shadow_meta:
        The ``profile_hygiene_shadow_meta`` dict from a pipeline result.
    max_penalized_fraction:
        Gate fails if ``profile_penalized_count / input_count`` exceeds this.
    max_abs_delta:
        Gate fails if any single insight loses more than this many confidence
        points (0-100 scale).

    Returns
    -------
    dict with keys:
        passed (bool), reason (str), penalized_fraction (float),
        max_abs_delta_observed (float)
    """
    if not shadow_meta or not isinstance(shadow_meta, dict):
        return {
            "passed": False,
            "reason": "shadow_meta_missing_or_invalid",
            "penalized_fraction": 0.0,
            "max_abs_delta_observed": 0.0,
        }

    if not shadow_meta.get("evaluated"):
        detail = shadow_meta.get("reason", "not_evaluated")
        return {
            "passed": False,
            "reason": f"shadow_not_evaluated: {detail}",
            "penalized_fraction": 0.0,
            "max_abs_delta_observed": 0.0,
        }

    input_count: int = shadow_meta.get("input_count", 0)
    penalized_count: int = shadow_meta.get("profile_penalized_count", 0)

    penalized_fraction = penalized_count / input_count if input_count > 0 else 0.0

    deltas: list[dict] = shadow_meta.get("confidence_deltas") or []
    max_delta_observed = 0.0
    for d in deltas:
        before = d.get("before_confidence", 0.0)
        after = d.get("after_confidence", 0.0)
        abs_delta = abs(before - after)
        if abs_delta > max_delta_observed:
            max_delta_observed = abs_delta

    if penalized_fraction >= max_penalized_fraction:
        return {
            "passed": False,
            "reason": (
                f"too_many_insights_penalized: {penalized_count}/{input_count} "
                f"({penalized_fraction:.1%}) >= threshold {max_penalized_fraction:.1%}"
            ),
            "penalized_fraction": penalized_fraction,
            "max_abs_delta_observed": max_delta_observed,
        }

    if max_delta_observed >= max_abs_delta:
        return {
            "passed": False,
            "reason": (
                f"confidence_drop_too_large: max delta {max_delta_observed:.1f} "
                f">= threshold {max_abs_delta:.1f}"
            ),
            "penalized_fraction": penalized_fraction,
            "max_abs_delta_observed": max_delta_observed,
        }

    return {
        "passed": True,
        "reason": "ok",
        "penalized_fraction": penalized_fraction,
        "max_abs_delta_observed": max_delta_observed,
    }

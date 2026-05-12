import math


def safe_confidence_0_100(value: object, default: float = 50.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default

    if math.isnan(parsed):
        return default
    if parsed == float("inf"):
        return 100.0
    if parsed == float("-inf"):
        return 0.0

    if parsed < 0:
        return 0.0
    if parsed > 100:
        return 100.0
    return parsed


def safe_confidence_from_insight(ins: dict, default: float = 50.0) -> float:
    if not isinstance(ins, dict):
        return default
    return safe_confidence_0_100(ins.get("confidence", default), default=default)

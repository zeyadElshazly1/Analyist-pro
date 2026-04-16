VALID_AGGREGATIONS = frozenset({"mean", "sum", "count", "min", "max", "median"})

# Frequency label → seasonal lag for autocorrelation check
FREQ_TO_LAG: dict[str, int] = {
    "minutely": 60,
    "hourly":   24,
    "daily":     7,
    "weekly":    4,
    "monthly":  12,
    "quarterly": 4,
    "yearly":    1,
}

# Frequency label → STL decomposition period
FREQ_TO_PERIOD: dict[str, int] = {
    "minutely": 60,
    "hourly":   24,
    "daily":     7,
    "weekly":    4,
    "monthly":  12,
    "quarterly": 4,
    "yearly":    1,
}

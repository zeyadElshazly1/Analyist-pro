"""
Runtime budget constants for the analysis pipeline.

These caps prevent O(n²) column combinations from making the insight engine
slow or unpredictable on wide datasets. Each detector picks up the relevant
constant and slices its column list before doing any expensive work.
"""

# Correlation: pairwise combinations grow as n*(n-1)/2 — cap tightly
MAX_CORR_COLS = 15          # numeric cols considered for pairwise correlation

# Segment: cat × num pairs; capped separately
MAX_SEG_CATS = 8            # categorical cols scanned for segment gaps
MAX_SEG_NUMS = 10           # numeric cols scanned per categorical col

# Binary-rate analysis: O(n) per column (no nested numeric loop), so we can
# afford a much wider scan than the O(n²) segment-gap detector.
MAX_BINARY_RATE_CATS = 20   # categorical cols scanned for binary rate gaps

# Univariate detectors (anomaly, distribution): linear in cols
MAX_UNIVARIATE_COLS = 20    # numeric cols for univariate anomaly / skewness

# Advanced detectors: expensive nested loops
MAX_ADV_NUMERIC = 6         # cols for interaction, Simpson's, concentration
MAX_ADV_CATEGORICAL = 3     # moderator cols for interaction / Simpson's

# Trend: linear regression per col
MAX_TREND_COLS = 15         # numeric cols tested for trend

# Leading indicators: lag correlation per pair
MAX_LEADING_PAIRS = 5       # numeric cols considered for leading-indicator pairs
MAX_LAG_DEPTH = 5           # maximum lag to test

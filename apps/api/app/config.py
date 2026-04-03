"""
Centralized configuration constants.
All magic numbers and thresholds live here — change once, affects everywhere.
"""

# ── File Upload ───────────────────────────────────────────────────────────────
MAX_UPLOAD_BYTES = 100 * 1024 * 1024   # 100 MB
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
UPLOAD_DIR = "uploads"

# ── Correlation Analysis ──────────────────────────────────────────────────────
MIN_CORRELATION = 0.3          # Minimum |r| to report a correlation
MAX_CORR_COLS = 20             # Max columns for full pairwise correlation
BH_ALPHA = 0.05                # Benjamini-Hochberg FDR threshold

# ── Anomaly Detection ─────────────────────────────────────────────────────────
ZSCORE_THRESHOLD = 3.0         # Standard Z-score outlier cutoff
ZSCORE_SKEWED_THRESHOLD = 3.5  # Relaxed threshold for skewed distributions
IQR_MULTIPLIER_NORMAL = 1.5    # IQR fence multiplier for normal distributions
IQR_MULTIPLIER_SKEWED = 3.0    # IQR fence multiplier for skewed distributions
SKEW_THRESHOLD = 1.0           # |skewness| above this = "skewed"
ISOLATION_MAX_CONTAMINATION = 0.1
ISOLATION_MIN_CONTAMINATION = 0.01
ISOLATION_N_ESTIMATORS = 100

# ── Insights Engine ───────────────────────────────────────────────────────────
MAX_INSIGHTS = 15              # Maximum insights returned per analysis
MIN_ROWS_FOR_INSIGHT = 10      # Minimum rows to compute an insight
MIN_ROWS_FOR_SEGMENT = 30      # Minimum group size for segment gap analysis
SEGMENT_RATIO_THRESHOLD = 1.5  # Min ratio for segment gap to be notable
CONCENTRATION_THRESHOLD = 0.5  # Top 10% must account for > 50% of total
INTERACTION_R_RANGE = 0.3      # Min correlation range across groups
LEADING_INDICATOR_MIN_R = 0.4  # Min |r| for a leading indicator
LEADING_INDICATOR_GAIN = 0.1   # Lag correlation must beat base by this margin
MAX_LAG = 5                    # Max lag periods for leading indicator search
SIMPSONS_FLIP_COUNT = 2        # Min groups where sign flips for Simpson's

# ── Profiler ──────────────────────────────────────────────────────────────────
NORMALITY_SHAPIRO_MAX = 5000   # Use Shapiro-Wilk up to this sample size
NORMALITY_SHAPIRO_SAMPLE = 2000  # Sample size for Shapiro on large cols
PROFILER_PATTERN_SAMPLE = 300  # Rows sampled for regex pattern detection
PROFILER_TOP_VALUES = 10       # Top N values shown for categorical columns
DATE_FRESHNESS_DAYS_FRESH = 7
DATE_FRESHNESS_DAYS_RECENT = 30
DATE_FRESHNESS_DAYS_STALE = 90

# ── AutoML ────────────────────────────────────────────────────────────────────
AUTOML_TEST_SIZE = 0.2
AUTOML_CV_FOLDS = 5
AUTOML_N_ESTIMATORS = 100
AUTOML_MAX_MISSING_COL_PCT = 0.7   # Drop columns with > 70% missing
AUTOML_MAX_UNIQUE_CLASSIFICATION = 20  # ≤ this unique values → classification

# ── Cleaner ───────────────────────────────────────────────────────────────────
HIGH_MISSING_DROP_THRESHOLD = 0.6   # Drop columns with > 60% missing
WINSOR_IQR_MULTIPLIER = 3.0         # Winsorization fence for skewed data
WINSOR_SIGMA_MULTIPLIER = 4.0       # Winsorization fence for normal data
BOOL_STANDARDIZATION_MIN_UNIQUE = 2
MAR_CORRELATION_THRESHOLD = 0.25
MNAR_SELF_CORRELATION_THRESHOLD = 0.3

# ── SQL Engine ────────────────────────────────────────────────────────────────
SQL_MAX_ROWS = 500

# ── Analysis Cache ────────────────────────────────────────────────────────────
CACHE_TTL_SECONDS = 3600       # Cache analysis results for 1 hour

# ── Cohorts ───────────────────────────────────────────────────────────────────
RFM_QUINTILES = 5              # Number of RFM scoring buckets

# ── Report ────────────────────────────────────────────────────────────────────
REPORT_MAX_INSIGHTS = 10       # Insights shown in exported report
REPORT_MAX_PROFILE_COLS = 20   # Columns profiled in exported report

"""
Chart generation budget constants.

All column/row limits that control how many items are processed per chart type
live here.  Change these values in one place to tune performance vs. coverage.
"""

MAX_TIMESERIES_DATES  = 2    # datetime columns considered for line charts
MAX_TIMESERIES_NUMS   = 3    # numeric columns per datetime column
MAX_TIMESERIES_POINTS = 200  # data points per line chart (sorted series truncated here)

MAX_HIST_COLS         = 4    # numeric columns rendered as histograms

MAX_CAT_BAR_COLS      = 3    # categorical columns rendered as bar charts
MAX_CAT_BAR_TOP       = 10   # top-N categories shown; remainder collapsed to "Other"

MAX_CAT_PIE_COLS      = 2    # categorical columns rendered as pie charts

MAX_SCATTER_COLS      = 6    # numeric columns considered for scatter pairs (C(6,2) = 15 pairs)
MAX_SCATTER_POINTS    = 300  # sampled points per scatter chart

MAX_HEATMAP_COLS      = 8    # numeric columns included in the correlation heatmap

MAX_BOXPLOT_OUTLIERS  = 20   # outlier dots per box-whisker group

MAX_CHARTS            = 10   # final output cap (top-scored charts returned)

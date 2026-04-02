import math
from datetime import datetime, date

import numpy as np
import pandas as pd


def to_jsonable(value):
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}

    if isinstance(value, list):
        return [to_jsonable(v) for v in value]

    if isinstance(value, tuple):
        return [to_jsonable(v) for v in value]

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)

    if isinstance(value, (np.bool_,)):
        return bool(value)

    if isinstance(value, (pd.Timestamp, datetime, date)):
        return str(value)

    # Only call pd.isna on scalar-like types to avoid "ambiguous truth value" errors
    if isinstance(value, (int, float, complex)):
        try:
            if math.isnan(value) or math.isinf(value):
                return None
        except (TypeError, ValueError):
            pass

    return value
"""Helpers for the HSLS:09 crosswalk and the cleaned file.

scaffold() puts functions/ on the import path, so notebooks import this with
`import hsls`. The R project keeps matching helpers in functions/hsls_crosswalk.R.
"""

import numpy as np
import pandas as pd


def codes(text: str) -> list[float]:
    """'-9;-8' as [-9, -8]. An empty cell gives no codes."""
    return [float(code) for code in text.split(";")] if text else []


def value_labels(text: str) -> dict[float, str]:
    """'1=City;2=Suburb' as {1: 'City', 2: 'Suburb'}."""
    if not text:
        return {}
    return {float(value): label for value, label in (pair.split("=", 1) for pair in text.split(";"))}


def missing_reasons(raw: pd.DataFrame, clean: pd.DataFrame, crosswalk: pd.DataFrame) -> pd.DataFrame:
    """Why each value in the clean file is missing, one column per variable.

    Each cell is one of:
    - "Observed": the clean value is present
    - "Nonresponse": the raw value is a nonresponse code or blank
    - "Logical skip": the raw value is a logical-skip code
    - "Outside the flag": the raw value is an answer, but the crosswalk's
      `within` flag is not 1 for this student

    A flag built from a logical skip (derive = applies) turns the skip into 0,
    so its skips count as observed.
    """
    reasons = {}
    for row in crosswalk.itertuples():
        source = raw[row.nces]
        observed = clean[row.name].notna()
        nonresponse = source.isin(codes(row.missing)) | source.isna()
        skipped = source.isin(codes(row.skip))
        reasons[row.name] = np.select(
            [observed, nonresponse, skipped],
            ["Observed", "Nonresponse", "Logical skip"],
            default="Outside the flag",
        )
    return pd.DataFrame(reasons, index=clean.index)


def weighted_mean_sd(x: pd.Series, weight: pd.Series) -> tuple[float, float]:
    """Mean and SD of x with weights, over the cases where both are present and the weight is above 0."""
    keep = x.notna() & weight.notna() & (weight > 0)
    x, weight = x[keep], weight[keep]
    mean = np.average(x, weights=weight)
    sd = np.sqrt(np.average((x - mean) ** 2, weights=weight))
    return float(mean), float(sd)

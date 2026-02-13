from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from keye.ingest.schema import InferredSchema


@dataclass(frozen=True)
class NormalizedResult:
    df: pd.DataFrame
    layout: str  # "long" or "wide_passthrough"
    period_column: str | None
    value_column: str | None


def _drop_all_null_columns(df: pd.DataFrame) -> pd.DataFrame:
    keep = [c for c in df.columns if not df[c].isna().all()]
    return df[keep]


def normalize_dataframe(df: pd.DataFrame, inferred: InferredSchema) -> NormalizedResult:
    """
    Normalization rules (POC):
    - Drop fully-empty columns
    - If "wide period" columns are detected, melt them into long format:
        dims... + period + value
      Otherwise, keep as-is.
    """
    df = _drop_all_null_columns(df)

    if inferred.period_columns_from_wide:
        id_vars = [c for c in df.columns if c not in inferred.period_columns_from_wide]
        long_df = df.melt(
            id_vars=id_vars,
            value_vars=inferred.period_columns_from_wide,
            var_name="period",
            value_name="value",
        )
        return NormalizedResult(df=long_df, layout="long", period_column="period", value_column="value")

    return NormalizedResult(df=df, layout="wide_passthrough", period_column=None, value_column=None)

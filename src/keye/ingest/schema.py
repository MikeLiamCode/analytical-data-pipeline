from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd


_PERIOD_NAME_RE = re.compile(
    r"^(?:"
    r"(?:q[1-4][ _-]?\d{2,4})"  # Q1-20, Q1 2020, etc
    r"|(?:\d{4}[ _-]?(?:q[1-4]|m\d{1,2}))"  # 2020Q1, 2020-M1
    r"|(?:\d{4}[-/]\d{1,2})"  # 2020-01
    r"|(?:\d{4})"  # 2020
    r")$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class InferredSchema:
    columns: dict[str, str]  # name -> logical type: categorical|numeric|datetime|other
    categorical: list[str]
    numeric: list[str]
    datetime: list[str]
    period_columns_from_wide: list[str]
    recommended_time_column: str | None


def _logical_type(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    # For object/string: treat low-cardinality as categorical
    if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
        return "categorical"
    return "other"


def infer_schema(df: pd.DataFrame) -> InferredSchema:
    columns: dict[str, str] = {}
    categorical: list[str] = []
    numeric: list[str] = []
    datetime_cols: list[str] = []

    for col in df.columns:
        t = _logical_type(df[col])
        columns[col] = t
        if t == "categorical":
            categorical.append(col)
        elif t == "numeric":
            numeric.append(col)
        elif t == "datetime":
            datetime_cols.append(col)

    # Heuristic: if there is a datetime-like column, prefer it as time.
    recommended_time = datetime_cols[0] if datetime_cols else None

    # Heuristic: period-like column names among numeric columns suggests "wide" period layout.
    period_columns = [c for c in df.columns if _PERIOD_NAME_RE.match(str(c).strip())]
    # Only consider them "wide period columns" if they look numeric.
    period_columns_from_wide = [c for c in period_columns if columns.get(c) == "numeric"]
    if recommended_time is None and period_columns_from_wide:
        recommended_time = "period"  # will be created during normalization

    return InferredSchema(
        columns=columns,
        categorical=categorical,
        numeric=numeric,
        datetime=datetime_cols,
        period_columns_from_wide=period_columns_from_wide,
        recommended_time_column=recommended_time,
    )


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    def clean(name: Any) -> str:
        s = str(name).strip()
        s = re.sub(r"[^\w]+", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s.lower() or "col"

    new_cols = []
    seen: dict[str, int] = {}
    for c in df.columns:
        base = clean(c)
        n = seen.get(base, 0)
        seen[base] = n + 1
        new_cols.append(base if n == 0 else f"{base}_{n+1}")
    df = df.copy()
    df.columns = new_cols
    return df

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Anomaly:
    kind: str
    message: str
    column: str | None = None
    severity: str = "warning"  # info|warning|error


def detect_anomalies(df: pd.DataFrame) -> list[Anomaly]:
    anomalies: list[Anomaly] = []

    if df.empty:
        return [Anomaly(kind="empty", message="Dataset has 0 rows.", severity="error")]

    # Column null-rate checks
    null_rates = df.isna().mean(numeric_only=False)
    for col, rate in null_rates.items():
        if rate >= 0.95:
            anomalies.append(
                Anomaly(
                    kind="high_null_rate",
                    column=str(col),
                    message=f"Column '{col}' is {rate:.0%} null.",
                    severity="warning",
                )
            )

    # Duplicate row check (sampled to avoid huge memory usage)
    sample = df if len(df) <= 200_000 else df.sample(200_000, random_state=0)
    dup_rate = float(sample.duplicated().mean())
    if dup_rate >= 0.05:
        anomalies.append(
            Anomaly(
                kind="duplicate_rows",
                message=f"~{dup_rate:.0%} duplicate rows in a 200k sample.",
                severity="info",
            )
        )

    # Numeric outliers (robust IQR)
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    for col in numeric_cols[:50]:  # guardrail
        s = df[col].dropna()
        if len(s) < 50:
            continue
        q1, q3 = np.percentile(s, [25, 75])
        iqr = q3 - q1
        if iqr == 0:
            continue
        lo, hi = q1 - 3 * iqr, q3 + 3 * iqr
        out_rate = float(((s < lo) | (s > hi)).mean())
        if out_rate >= 0.01:
            anomalies.append(
                Anomaly(
                    kind="outliers",
                    column=str(col),
                    message=f"Column '{col}' has ~{out_rate:.1%} extreme outliers (IQR rule).",
                    severity="info",
                )
            )

    return anomalies

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import duckdb
import pandas as pd

from keye.paths import StoragePaths, default_paths
from keye.util import sha256_file, utc_now_iso, write_json


Bucket = Literal[0.1, 0.2, 0.5]


@dataclass(frozen=True)
class ConcentrationParams:
    group_by: str
    value: str
    time: str | None = None  # column name for time axis (optional)
    buckets: tuple[Bucket, ...] = (0.1, 0.2, 0.5)


def _quote_ident(name: str) -> str:
    # DuckDB uses standard SQL identifier quoting with double quotes.
    # This prevents SQL injection via column names.
    return '"' + name.replace('"', '""') + '"'


def _concentration_for_period(group_sums: pd.DataFrame, buckets: tuple[Bucket, ...]) -> dict[str, Any]:
    """
    group_sums: columns [group_by, value], sorted desc by value.
    Returns mapping bucket_label -> {count, sum}.
    """
    n = len(group_sums)
    out: dict[str, Any] = {}
    total = float(group_sums["value"].sum())
    for b in buckets:
        k = max(1, math.ceil(b * n))
        s = float(group_sums["value"].head(k).sum())
        out[f"top_{int(b*100)}"] = {"count": k, "sum": s}
    out["total"] = {"count": n, "sum": total}
    return out


def run_concentration(
    dataset_id: str,
    params: ConcentrationParams,
    *,
    paths: StoragePaths | None = None,
) -> dict[str, Any]:
    """
    Produces a wide table:
      rows: Top 10/20/50% (count) + Total
      cols: per period (if time is present) else single "all"
    """
    paths = paths or default_paths()
    parquet_path = paths.normalized_dir / dataset_id / "data.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"Unknown dataset_id={dataset_id}")

    con = duckdb.connect()
    try:
        if params.time:
            q = f"""
              SELECT
                CAST({_quote_ident(params.time)} AS VARCHAR) AS period,
                {_quote_ident(params.group_by)} AS grp,
                SUM(CAST({_quote_ident(params.value)} AS DOUBLE)) AS value
              FROM read_parquet(?)
              WHERE {_quote_ident(params.group_by)} IS NOT NULL
              GROUP BY 1, 2
            """
            agg = con.execute(q, [str(parquet_path)]).df()
        else:
            q = f"""
              SELECT
                'all' AS period,
                {_quote_ident(params.group_by)} AS grp,
                SUM(CAST({_quote_ident(params.value)} AS DOUBLE)) AS value
              FROM read_parquet(?)
              WHERE {_quote_ident(params.group_by)} IS NOT NULL
              GROUP BY 1, 2
            """
            agg = con.execute(q, [str(parquet_path)]).df()
    finally:
        con.close()

    agg = agg.dropna(subset=["value"])
    periods = sorted(agg["period"].unique().tolist())

    rows: list[dict[str, Any]] = []
    # compute per period
    per_period_results: dict[str, dict[str, Any]] = {}
    for p in periods:
        g = agg.loc[agg["period"] == p, ["grp", "value"]].sort_values("value", ascending=False)
        per_period_results[p] = _concentration_for_period(g.rename(columns={"grp": "group_by"}), params.buckets)

    # construct output table (bucket rows, period columns)
    def row_label(b: Bucket, count: int) -> str:
        return f"Top {int(b*100)}% ({count})"

    for b in params.buckets:
        # counts can vary by period; use count from first period for label, but also return counts separately
        first = per_period_results[periods[0]][f"top_{int(b*100)}"]
        row: dict[str, Any] = {"bucket": row_label(b, int(first["count"]))}
        row_counts: dict[str, int] = {}
        for p in periods:
            item = per_period_results[p][f"top_{int(b*100)}"]
            row[p] = item["sum"]
            row_counts[p] = int(item["count"])
        row["_counts"] = row_counts
        rows.append(row)

    total_row: dict[str, Any] = {"bucket": "Total"}
    for p in periods:
        total_row[p] = per_period_results[p]["total"]["sum"]
    rows.append(total_row)

    # Persist analysis + audit manifest
    analysis_id = str(uuid.uuid4())
    out_dir = paths.analyses_dir / dataset_id / analysis_id
    out_dir.mkdir(parents=True, exist_ok=True)
    result_df = pd.DataFrame(rows)
    result_path = out_dir / "result.parquet"
    result_df.to_parquet(result_path, index=False)

    audit = {
        "analysis_id": analysis_id,
        "dataset_id": dataset_id,
        "created_at": utc_now_iso(),
        "type": "concentration",
        "params": {
            "group_by": params.group_by,
            "value": params.value,
            "time": params.time,
            "buckets": list(params.buckets),
        },
        "inputs": {
            "normalized_parquet_path": str(parquet_path),
            "normalized_parquet_sha256": sha256_file(parquet_path),
        },
        "outputs": {
            "result_parquet_path": str(result_path),
            "result_parquet_sha256": sha256_file(result_path),
        },
        "calculation_steps": [
            "Aggregate SUM(value) by (period, group).",
            "Sort groups descending within each period.",
            "For each bucket b in {10,20,50}%: take top ceil(b * num_groups) and sum.",
            "Also compute Total as sum across all groups.",
        ],
        "notes": [
            "Bucket counts are computed per period; the table label uses the first period's count.",
            "Per-period bucket counts are included in each row under _counts.",
        ],
    }
    write_json(out_dir / "audit.json", audit)

    return {
        "analysis_id": analysis_id,
        "dataset_id": dataset_id,
        "periods": periods,
        "rows": rows,
        "audit": audit,
    }

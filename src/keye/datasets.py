from __future__ import annotations

import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from keye.anomalies import detect_anomalies
from keye.ingest.excel import read_excel_first_sheet
from keye.ingest.normalize import normalize_dataframe
from keye.ingest.schema import InferredSchema, infer_schema, normalize_column_names
from keye.paths import StoragePaths, default_paths
from keye.util import read_json, sha256_file, utc_now_iso, write_json


def _dataset_dirs(paths: StoragePaths, dataset_id: str) -> tuple[Path, Path]:
    raw = paths.raw_dir / dataset_id
    norm = paths.normalized_dir / dataset_id
    raw.mkdir(parents=True, exist_ok=True)
    norm.mkdir(parents=True, exist_ok=True)
    return raw, norm


def ingest_excel(path: Path, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    paths = paths or default_paths()
    dataset_id = str(uuid.uuid4())
    raw_dir, norm_dir = _dataset_dirs(paths, dataset_id)

    # Persist raw upload
    raw_path = raw_dir / "source.xlsx"
    raw_path.write_bytes(path.read_bytes())
    raw_hash = sha256_file(raw_path)

    # Read + normalize
    df = read_excel_first_sheet(raw_path)
    df = normalize_column_names(df)
    inferred_before = infer_schema(df)
    normalized = normalize_dataframe(df, inferred_before)
    inferred_after = infer_schema(normalized.df)
    anomalies = detect_anomalies(normalized.df)

    # Persist normalized parquet
    parquet_path = norm_dir / "data.parquet"
    normalized.df.to_parquet(parquet_path, index=False)
    parquet_hash = sha256_file(parquet_path)

    manifest = {
        "dataset_id": dataset_id,
        "created_at": utc_now_iso(),
        "source": {
            "filename": path.name,
            "sha256": raw_hash,
        },
        "normalized": {
            "parquet_path": str(parquet_path),
            "sha256": parquet_hash,
            "layout": normalized.layout,
            "period_column": normalized.period_column,
            "value_column": normalized.value_column,
        },
        "schema": {
            "before": asdict(inferred_before),
            "after": asdict(inferred_after),
        },
        "anomalies": [asdict(a) for a in anomalies],
    }
    write_json(norm_dir / "manifest.json", manifest)

    return manifest


def load_manifest(dataset_id: str, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    paths = paths or default_paths()
    manifest_path = paths.normalized_dir / dataset_id / "manifest.json"
    return read_json(manifest_path)


def preview_dataset(dataset_id: str, limit: int = 20, *, paths: StoragePaths | None = None) -> list[dict[str, Any]]:
    paths = paths or default_paths()
    parquet_path = paths.normalized_dir / dataset_id / "data.parquet"
    con = duckdb.connect()
    try:
        df = con.execute("SELECT * FROM read_parquet(?) LIMIT ?", [str(parquet_path), int(limit)]).df()
    finally:
        con.close()
    return df.to_dict(orient="records")

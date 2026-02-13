# Keye POC: Excel → Normalized Data → Concentration Analysis

This repo is a lightweight, extensible first version of an analytical data pipeline:

- Upload **Excel** files (first sheet by default)
- Automatically **infer schema**, **normalize**, and run **basic anomaly checks**
- Run an **auditable concentration analysis** (Top 10/20/50% of groups by value) across time periods

## Architecture (POC)

**Storage layout**

- `data/raw/<dataset_id>/source.xlsx` — immutable upload
- `data/normalized/<dataset_id>/data.parquet` — normalized dataset
- `data/normalized/<dataset_id>/manifest.json` — inferred schema, detected time axis, anomalies, fingerprints
- `data/analyses/<dataset_id>/<analysis_id>/*` — analysis outputs + audit manifest

**Execution**

- FastAPI service (`src/keye_api/main.py`) provides upload, preview, and analysis endpoints
- DuckDB is used for scalable aggregations over Parquet (keeps a path to scale toward 10M–100M rows)

**Why this direction**

- Parquet + DuckDB gives a stable “analytical substrate” without committing to a heavyweight warehouse early
- Manifests provide a simple, inspectable form of lineage/auditability from day 1

## Run (Docker)

```bash
docker compose up --build
```

Service: `http://localhost:8000`

OpenAPI docs: `http://localhost:8000/docs`

## Run (Local Python)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn keye_api.main:app --reload
```

## API usage

### 1) Upload

```bash
curl -F "file=@/path/to/file.xlsx" http://localhost:8000/datasets/upload
```

Response includes `dataset_id`, inferred columns, detected time axis (if any), and anomalies.

### 2) Preview

```bash
curl "http://localhost:8000/datasets/<dataset_id>/preview?limit=20"
```

### 3) Concentration analysis

Pick:
- `group_by`: categorical column
- `value`: numeric column (or `value` if the file was normalized from wide-period columns)

```bash
curl -X POST "http://localhost:8000/datasets/<dataset_id>/analyses/concentration" \\
  -H "Content-Type: application/json" \\
  -d '{
    "group_by":"customer_code",
    "value":"revenue",
    "time":"year"
  }'
```

## Trade-offs (explicit)

- This POC uses heuristic schema inference and time-axis detection; it is intentionally **not** fully
  configurable yet (future: per-client ingestion specs + regression tests).
- Anomaly detection is basic (null rates, duplicates, outliers). It’s designed to be auditable and
  extensible rather than exhaustive on day 1.
- For very large Excel files, ingestion should move to streaming conversion (or require CSV/Parquet);
  the normalized substrate is already positioned for that transition.

## Next steps (scalability)

- Add dataset versioning (append-only, content-addressed manifests)
- Persist DuckDB tables/views per dataset for faster repeated analyses
- Introduce a “transformation registry” with named, tested transforms (dbt-style)
- Add an AI “insights” layer that only consumes manifests + derived tables (bounded + auditable)

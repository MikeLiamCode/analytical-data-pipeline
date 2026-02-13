from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from keye.analysis.concentration import ConcentrationParams, run_concentration
from keye.datasets import ingest_excel, preview_dataset

app = FastAPI(title="Keye POC API", version="0.1.0")


class ConcentrationRequest(BaseModel):
    group_by: str = Field(..., description="Categorical column to group by")
    value: str = Field(..., description="Numeric column to aggregate (sum)")
    time: str | None = Field(None, description="Optional time/period column name")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")
    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx supported in this POC.")

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(await file.read())

    try:
        manifest = ingest_excel(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to ingest file: {e}") from e
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    return manifest


@app.get("/datasets/{dataset_id}/preview")
def preview(dataset_id: str, limit: int = 20) -> dict[str, Any]:
    try:
        rows = preview_dataset(dataset_id, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"dataset_id": dataset_id, "limit": limit, "rows": rows}


@app.post("/datasets/{dataset_id}/analyses/concentration")
def concentration(dataset_id: str, req: ConcentrationRequest) -> dict[str, Any]:
    try:
        res = run_concentration(
            dataset_id,
            ConcentrationParams(group_by=req.group_by, value=req.value, time=req.time),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return res

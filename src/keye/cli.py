from __future__ import annotations

from pathlib import Path

import typer
from rich import print

from keye.analysis.concentration import ConcentrationParams, run_concentration
from keye.datasets import ingest_excel, preview_dataset

app = typer.Typer(no_args_is_help=True)


@app.command()
def ingest(path: Path):
    """Ingest an Excel file and write normalized outputs under ./data."""
    manifest = ingest_excel(path)
    print(manifest)


@app.command()
def preview(dataset_id: str, limit: int = 20):
    """Preview the first N rows of a normalized dataset."""
    rows = preview_dataset(dataset_id, limit=limit)
    print(rows)


@app.command()
def concentration(dataset_id: str, group_by: str, value: str, time: str | None = None):
    """Run concentration analysis for a dataset."""
    res = run_concentration(dataset_id, ConcentrationParams(group_by=group_by, value=value, time=time))
    print(res)

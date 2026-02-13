from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_excel_first_sheet(path: Path) -> pd.DataFrame:
    # POC: first sheet only; future: allow user selection.
    xl = pd.ExcelFile(path)
    sheet = xl.sheet_names[0]
    df = xl.parse(sheet)
    return df

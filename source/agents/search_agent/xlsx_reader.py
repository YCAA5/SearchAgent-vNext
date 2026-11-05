
"""
Search Agent - XLSX Reader v0.1

Features:
- Multiple worksheet extraction
- Cell value extraction
- Formula extraction
- Cached formula result extraction
- Empty worksheet detection
- Row and column information

Original XLSX files are never modified.
"""

from datetime import date, datetime, time, timedelta
from pathlib import Path

from openpyxl import load_workbook


def normalize_value(value):
    """Convert Excel values into JSON-compatible values."""

    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    if isinstance(value, timedelta):
        return str(value)

    return value


def read_xlsx(file_path: str | Path) -> dict:
    """Extract worksheets, cell values and formulas."""

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() != ".xlsx":
        raise ValueError("File must have an XLSX extension.")

    workbook = load_workbook(
        path,
        data_only=False,
        read_only=False
    )

    cached_workbook = load_workbook(
        path,
        data_only=True,
        read_only=False
    )

    worksheets = []

    try:
        for sheet in workbook.worksheets:
            cached_sheet = cached_workbook[sheet.title]

            rows = []
            non_empty_cells = 0
            formula_count = 0

            for row in sheet.iter_rows():
                cells = []

                for cell in row:
                    if cell.value is None:
                        continue

                    non_empty_cells += 1

                    is_formula = cell.data_type == "f"

                    if is_formula:
                        formula_count += 1

                    cached_value = (
                        cached_sheet[cell.coordinate].value
                        if is_formula
                        else None
                    )

                    cells.append({
                        "coordinate": cell.coordinate,
                        "value": (
                            None
                            if is_formula
                            else normalize_value(cell.value)
                        ),
                        "formula": (
                            cell.value
                            if is_formula
                            else None
                        ),
                        "cached_value": normalize_value(cached_value),
                        "data_type": cell.data_type,
                    })

                if cells:
                    rows.append({
                        "row_number": row[0].row,
                        "cells": cells,
                    })

            worksheets.append({
                "sheet_name": sheet.title,
                "max_row": sheet.max_row,
                "max_column": sheet.max_column,
                "rows": rows,
                "non_empty_cells": non_empty_cells,
                "formula_count": formula_count,
                "is_empty": non_empty_cells == 0,
            })

    finally:
        workbook.close()
        cached_workbook.close()

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_type": "xlsx",
        "sheet_count": len(worksheets),
        "worksheets": worksheets,
    }
def test_read_file_dispatches_xlsx(sample_xlsx):
    from agents.search_agent.text_reader import read_file

    result = read_file(sample_xlsx)

    assert result["file_type"] == "xlsx"
    assert result["sheet_count"] == 3
    assert result["worksheets"][0]["sheet_name"] == "Ürünler"
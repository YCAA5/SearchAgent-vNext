
import zipfile
from datetime import datetime

import pytest
from openpyxl import Workbook

from agents.search_agent.xlsx_reader import read_xlsx


@pytest.fixture
def sample_xlsx(tmp_path):
    """Create a sample Excel workbook with multiple worksheets."""

    file_path = tmp_path / "test_document.xlsx"

    workbook = Workbook()

    sheet1 = workbook.active
    sheet1.title = "Ürünler"

    sheet1["A1"] = "Ürün"
    sheet1["B1"] = "Fiyat"
    sheet1["C1"] = "Adet"
    sheet1["D1"] = "Toplam"

    sheet1["A2"] = "Klavye"
    sheet1["B2"] = 1500
    sheet1["C2"] = 2
    sheet1["D2"] = "=B2*C2"

    sheet1["A3"] = "Fare"
    sheet1["B3"] = 750
    sheet1["C3"] = 3
    sheet1["D3"] = "=B3*C3"

    sheet2 = workbook.create_sheet("Tarihler")

    sheet2["A1"] = "Tarih"
    sheet2["A2"] = datetime(2026, 11, 2)

    workbook.create_sheet("Boş Sayfa")

    workbook.save(file_path)

    return file_path


def test_read_xlsx(sample_xlsx):
    result = read_xlsx(sample_xlsx)

    assert result["file_type"] == "xlsx"
    assert result["sheet_count"] == 3


def test_worksheet_names(sample_xlsx):
    result = read_xlsx(sample_xlsx)

    names = [
        sheet["sheet_name"]
        for sheet in result["worksheets"]
    ]

    assert names == ["Ürünler", "Tarihler", "Boş Sayfa"]


def test_cell_values(sample_xlsx):
    result = read_xlsx(sample_xlsx)

    sheet = result["worksheets"][0]

    cells = {
        cell["coordinate"]: cell
        for row in sheet["rows"]
        for cell in row["cells"]
    }

    assert cells["A2"]["value"] == "Klavye"
    assert cells["B2"]["value"] == 1500
    assert cells["C2"]["value"] == 2


def test_formula_extraction(sample_xlsx):
    result = read_xlsx(sample_xlsx)

    sheet = result["worksheets"][0]

    cells = {
        cell["coordinate"]: cell
        for row in sheet["rows"]
        for cell in row["cells"]
    }

    assert cells["D2"]["formula"] == "=B2*C2"
    assert cells["D2"]["data_type"] == "f"
    assert cells["D2"]["value"] is None


def test_cached_formula_value(sample_xlsx):
    result = read_xlsx(sample_xlsx)

    sheet = result["worksheets"][0]

    cells = {
        cell["coordinate"]: cell
        for row in sheet["rows"]
        for cell in row["cells"]
    }

    # openpyxl does not calculate formulas.
    # A newly created workbook has no cached formula result.
    assert cells["D2"]["cached_value"] is None


def test_empty_worksheet_detection(sample_xlsx):
    result = read_xlsx(sample_xlsx)

    empty_sheet = result["worksheets"][2]

    assert empty_sheet["is_empty"] is True
    assert empty_sheet["non_empty_cells"] == 0


def test_non_empty_cell_count(sample_xlsx):
    result = read_xlsx(sample_xlsx)

    sheet = result["worksheets"][0]

    assert sheet["non_empty_cells"] == 12
    assert sheet["formula_count"] == 2


def test_date_normalization(sample_xlsx):
    result = read_xlsx(sample_xlsx)

    sheet = result["worksheets"][1]

    cells = {
        cell["coordinate"]: cell
        for row in sheet["rows"]
        for cell in row["cells"]
    }

    assert (
        cells["A2"]["value"]
        == "2026-11-02T00:00:00"
    )


def test_missing_xlsx():
    with pytest.raises(FileNotFoundError):
        read_xlsx("missing_document.xlsx")


def test_invalid_extension(tmp_path):
    file_path = tmp_path / "document.txt"

    file_path.write_text(
        "This is not an Excel file.",
        encoding="utf-8"
    )

    with pytest.raises(ValueError):
        read_xlsx(file_path)


def test_corrupted_xlsx(tmp_path):
    file_path = tmp_path / "corrupted.xlsx"

    file_path.write_bytes(
        b"This is not a valid XLSX file."
    )

    with pytest.raises(zipfile.BadZipFile):
        read_xlsx(file_path)

def test_read_file_dispatches_xlsx(sample_xlsx):
    from agents.search_agent.text_reader import read_file

    result = read_file(sample_xlsx)

    assert result["file_type"] == "xlsx"
    assert result["sheet_count"] == 3
    assert result["worksheets"][0]["sheet_name"] == "Ürünler"

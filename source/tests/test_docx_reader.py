
from pathlib import Path

import pytest
import zipfile
from docx import Document
from agents.search_agent.text_reader import read_file

from agents.search_agent.docx_reader import read_docx


@pytest.fixture
def sample_docx(tmp_path):
    """Create a sample DOCX with paragraphs and a table."""

    file_path = tmp_path / "test_document.docx"

    document = Document()

    document.add_heading("Search Agent DOCX Testi", level=1)

    document.add_paragraph(
        "Türkçe karakterler: ğ ü ş ı ö ç"
    )

    document.add_paragraph(
        "Bu bir normal paragraftır."
    )

    table = document.add_table(rows=2, cols=2)

    table.cell(0, 0).text = "Ürün"
    table.cell(0, 1).text = "Fiyat"
    table.cell(1, 0).text = "Klavye"
    table.cell(1, 1).text = "1500 TL"

    document.save(file_path)

    return file_path


def test_read_docx(sample_docx):
    result = read_docx(sample_docx)

    assert result["file_type"] == "docx"
    assert result["paragraph_count"] == 3
    assert result["table_count"] == 1


def test_docx_paragraph_content(sample_docx):
    result = read_docx(sample_docx)

    assert (
        result["paragraphs"][0]["text"]
        == "Search Agent DOCX Testi"
    )

    assert (
        result["paragraphs"][0]["style"]
        == "Heading 1"
    )


def test_turkish_characters(sample_docx):
    result = read_docx(sample_docx)

    assert (
        "ğ ü ş ı ö ç"
        in result["paragraphs"][1]["text"]
    )


def test_docx_table_content(sample_docx):
    result = read_docx(sample_docx)

    table = result["tables"][0]

    assert table["row_count"] == 2
    assert table["column_count"] == 2
    assert table["rows"][0] == ["Ürün", "Fiyat"]
    assert table["rows"][1] == ["Klavye", "1500 TL"]


def test_docx_character_count(sample_docx):
    result = read_docx(sample_docx)

    paragraph_chars = sum(
        len(item["text"])
        for item in result["paragraphs"]
    )

    table_chars = sum(
        len(cell)
        for table in result["tables"]
        for row in table["rows"]
        for cell in row
    )

    assert result["total_characters"] == (
        paragraph_chars + table_chars
    )


def test_missing_docx():
    with pytest.raises(FileNotFoundError):
        read_docx("missing_document.docx")


def test_invalid_extension(tmp_path):
    file_path = tmp_path / "document.txt"

    file_path.write_text(
        "This is not a DOCX file.",
        encoding="utf-8"
    )

    with pytest.raises(ValueError):
        read_docx(file_path)


def test_corrupted_docx(tmp_path):
    file_path = tmp_path / "corrupted.docx"

    file_path.write_bytes(
        b"This is not a valid DOCX file."
    )

    with pytest.raises(zipfile.BadZipFile):
        read_docx(file_path)
        
def test_read_file_dispatches_docx(sample_docx):
    result = read_file(sample_docx)

    assert result["file_type"] == "docx"
    assert result["paragraph_count"] == 3
    assert result["table_count"] == 1
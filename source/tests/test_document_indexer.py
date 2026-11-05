import sqlite3

from database.document_indexer import initialize_database


def test_initialize_database_creates_tables(tmp_path):
    db_path = tmp_path / "test_index.db"

    initialize_database(db_path)

    connection = sqlite3.connect(db_path)

    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }

    connection.close()

    assert "documents" in tables
    assert "document_search" in tables
    assert "folders" in tables

def test_index_document_saves_document(tmp_path):
    from database.document_indexer import index_document

    db_path = tmp_path / "test_index.db"
    initialize_database(db_path)

    document = {
        "file_name": "deneme.txt",
        "file_path": str(tmp_path / "deneme.txt"),
        "file_type": "txt",
        "file_size": 120,
        "modified_at": "2026-11-02T10:00:00+03:00",
        "content": "Search Agent Türkçe belge indeksleme testi."
    }

    index_document(db_path, document)

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT file_name, file_path, file_type,
                   file_size, modified_at, content
            FROM documents
            """
        ).fetchone()

    assert row is not None
    assert row[0] == "deneme.txt"
    assert row[2] == "txt"
    assert row[3] == 120
    assert "Türkçe belge indeksleme testi" in row[5]

def test_index_document_does_not_create_duplicates(tmp_path):
    from database.document_indexer import index_document

    db_path = tmp_path / "test_index.db"
    initialize_database(db_path)

    document = {
        "file_name": "deneme.txt",
        "file_path": str(tmp_path / "deneme.txt"),
        "file_type": "txt",
        "file_size": 120,
        "modified_at": "2026-11-02T10:00:00+03:00",
        "content": "İlk içerik."
    }

    index_document(db_path, document)
    index_document(db_path, document)

    with sqlite3.connect(db_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]

    assert count == 1

def test_index_document_updates_existing_document(tmp_path):
    from database.document_indexer import index_document

    db_path = tmp_path / "test_index.db"
    initialize_database(db_path)

    document = {
        "file_name": "deneme.txt",
        "file_path": str(tmp_path / "deneme.txt"),
        "file_type": "txt",
        "file_size": 120,
        "modified_at": "2026-11-02T10:00:00+03:00",
        "content": "Eski belge içeriği."
    }

    index_document(db_path, document)

    document["file_size"] = 250
    document["content"] = "Yeni belge içeriği."

    index_document(db_path, document)

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT file_size, content
            FROM documents
            """
        ).fetchall()

    assert len(rows) == 1
    assert rows[0][0] == 250
    assert rows[0][1] == "Yeni belge içeriği."

def test_index_document_updates_full_text_search(tmp_path):
    from database.document_indexer import index_document

    db_path = tmp_path / "test_index.db"
    initialize_database(db_path)

    document = {
        "file_name": "deneme.txt",
        "file_path": str(tmp_path / "deneme.txt"),
        "file_type": "txt",
        "file_size": 120,
        "modified_at": "2026-11-02T10:00:00+03:00",
        "content": "eskiicerik"
    }

    index_document(db_path, document)

    with sqlite3.connect(db_path) as connection:
        old_result = connection.execute(
            """
            SELECT rowid
            FROM document_search
            WHERE document_search MATCH ?
            """,
            ("eskiicerik",)
        ).fetchall()

    assert len(old_result) == 1

    document["content"] = "yeniicerik"
    index_document(db_path, document)

    with sqlite3.connect(db_path) as connection:
        old_result = connection.execute(
            """
            SELECT rowid
            FROM document_search
            WHERE document_search MATCH ?
            """,
            ("eskiicerik",)
        ).fetchall()

        new_result = connection.execute(
            """
            SELECT rowid
            FROM document_search
            WHERE document_search MATCH ?
            """,
            ("yeniicerik",)
        ).fetchall()

    assert len(old_result) == 0
    assert len(new_result) == 1

def test_calculate_file_hash(tmp_path):
    from database.document_indexer import calculate_file_hash

    file_path = tmp_path / "deneme.txt"
    file_path.write_text("Search Agent", encoding="utf-8")

    file_hash = calculate_file_hash(file_path)

    assert len(file_hash) == 64
    assert file_hash == calculate_file_hash(file_path)

def test_index_document_saves_file_hash(tmp_path):
    import sqlite3
    from database.document_indexer import (
        index_document,
        calculate_file_hash,
    )

    file_path = tmp_path / "deneme.txt"
    file_path.write_text("Search Agent", encoding="utf-8")

    db_path = tmp_path / "index.db"

    document = {
        "file_name": "deneme.txt",
        "file_path": str(file_path),
        "file_type": ".txt",
        "file_size": file_path.stat().st_size,
        "modified_at": None,
        "content": "Search Agent",
    }

    index_document(db_path, document)

    with sqlite3.connect(db_path) as connection:
        result = connection.execute(
            "SELECT file_hash FROM documents WHERE file_path = ?",
            (str(file_path),)
        ).fetchone()

    assert result is not None
    assert result[0] == calculate_file_hash(file_path)


def test_index_document_skips_unchanged_file(tmp_path):
    import sqlite3
    from database.document_indexer import index_document

    file_path = tmp_path / "deneme.txt"
    file_path.write_text("Search Agent", encoding="utf-8")

    db_path = tmp_path / "index.db"

    document = {
        "file_name": "deneme.txt",
        "file_path": str(file_path),
        "file_type": ".txt",
        "file_size": file_path.stat().st_size,
        "modified_at": None,
        "content": "Search Agent",
    }

    index_document(db_path, document)

    # Mark the first indexing time with a known value.
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE documents SET indexed_at = ? WHERE file_path = ?",
            ("2000-01-01T00:00:00", str(file_path))
        )

    # The file itself is unchanged, but the supplied content differs.
    updated_document = document.copy()
    updated_document["content"] = "This content should not be saved"

    index_document(db_path, updated_document)

    with sqlite3.connect(db_path) as connection:
        result = connection.execute(
            """
            SELECT content, indexed_at
            FROM documents
            WHERE file_path = ?
            """,
            (str(file_path),)
        ).fetchone()

    assert result[0] == "Search Agent"
    assert result[1] == "2000-01-01T00:00:00"


def test_index_directory_indexes_txt_files(tmp_path):
    import sqlite3
    from database.document_indexer import index_directory

    source_dir = tmp_path / "documents"
    source_dir.mkdir()

    file_path = source_dir / "deneme.txt"
    file_path.write_text(
        "Search Agent integration test",
        encoding="utf-8"
    )

    db_path = tmp_path / "index.db"

    index_directory(source_dir, db_path)

    with sqlite3.connect(db_path) as connection:
        result = connection.execute(
            """
            SELECT file_name, file_type, content
            FROM documents
            WHERE file_path = ?
            """,
            (str(file_path.resolve()),)
        ).fetchone()

    assert result is not None
    assert result[0] == "deneme.txt"
    assert result[1] == ".txt"
    assert "Search Agent integration test" in result[2]


def test_index_directory_skips_unchanged_txt_files(tmp_path):
    import sqlite3
    from database.document_indexer import index_directory

    source_dir = tmp_path / "documents"
    source_dir.mkdir()

    file_path = source_dir / "deneme.txt"
    file_path.write_text("Search Agent", encoding="utf-8")

    db_path = tmp_path / "index.db"

    index_directory(source_dir, db_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE documents SET indexed_at = ? WHERE file_path = ?",
            ("2000-01-01T00:00:00", str(file_path.resolve()))
        )

    index_directory(source_dir, db_path)

    with sqlite3.connect(db_path) as connection:
        result = connection.execute(
            """
            SELECT indexed_at
            FROM documents
            WHERE file_path = ?
            """,
            (str(file_path.resolve()),)
        ).fetchone()

    assert result[0] == "2000-01-01T00:00:00"

def test_index_directory_indexes_csv_files(tmp_path):
    import sqlite3
    from database.document_indexer import index_directory

    source_dir = tmp_path / "documents"
    source_dir.mkdir()

    file_path = source_dir / "veriler.csv"
    file_path.write_text(
        "Ad,Meslek\nMurat,Tasarımcı\n",
        encoding="utf-8"
    )

    db_path = tmp_path / "index.db"

    index_directory(source_dir, db_path)

    with sqlite3.connect(db_path) as connection:
        result = connection.execute(
            """
            SELECT content
            FROM documents
            WHERE file_path = ?
            """,
            (str(file_path.resolve()),)
        ).fetchone()

    assert result is not None
    assert "Murat" in result[0]
    assert "Tasarımcı" in result[0]

def test_index_directory_indexes_docx_files(tmp_path):
    import sqlite3
    from docx import Document
    from database.document_indexer import index_directory

    source_dir = tmp_path / "documents"
    source_dir.mkdir()

    file_path = source_dir / "rapor.docx"

    doc = Document()
    doc.add_heading("Search Agent Raporu", level=1)
    doc.add_paragraph("Belge indeksleme entegrasyon testi.")
    doc.save(file_path)

    db_path = tmp_path / "index.db"

    index_directory(source_dir, db_path)

    with sqlite3.connect(db_path) as connection:
        result = connection.execute(
            """
            SELECT content
            FROM documents
            WHERE file_path = ?
            """,
            (str(file_path.resolve()),)
        ).fetchone()

    assert result is not None
    assert "Search Agent Raporu" in result[0]
    assert "Belge indeksleme entegrasyon testi." in result[0]

def test_index_directory_indexes_pdf_files(tmp_path):
    import sqlite3
    import fitz
    from database.document_indexer import index_directory

    source_dir = tmp_path / "documents"
    source_dir.mkdir()

    file_path = source_dir / "rapor.pdf"

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "PDF Search Agent integration test")
    pdf.save(file_path)
    pdf.close()

    db_path = tmp_path / "index.db"

    index_directory(source_dir, db_path)

    with sqlite3.connect(db_path) as connection:
        result = connection.execute(
            """
            SELECT content
            FROM documents
            WHERE file_path = ?
            """,
            (str(file_path.resolve()),)
        ).fetchone()

    assert result is not None
    assert "PDF Search Agent integration test" in result[0]

def test_index_directory_indexes_xlsx_files(tmp_path):
    import sqlite3
    from openpyxl import Workbook
    from database.document_indexer import index_directory

    source_dir = tmp_path / "documents"
    source_dir.mkdir()

    file_path = source_dir / "veriler.xlsx"

    workbook = Workbook()
    worksheet = workbook.active
    worksheet["A1"] = "Proje"
    worksheet["B1"] = "Search Agent"
    worksheet["A2"] = "Durum"
    worksheet["B2"] = "Entegrasyon testi"
    workbook.save(file_path)

    db_path = tmp_path / "index.db"

    index_directory(source_dir, db_path)

    with sqlite3.connect(db_path) as connection:
        result = connection.execute(
            """
            SELECT content
            FROM documents
            WHERE file_path = ?
            """,
            (str(file_path.resolve()),)
        ).fetchone()

    assert result is not None
    assert "Search Agent" in result[0]
    assert "Entegrasyon testi" in result[0]

def test_index_directory_indexes_pptx_files(tmp_path):
    import sqlite3
    from pptx import Presentation
    from pptx.util import Inches
    from database.document_indexer import index_directory

    source_dir = tmp_path / "documents"
    source_dir.mkdir()

    file_path = source_dir / "sunum.pptx"

    presentation = Presentation()
    slide = presentation.slides.add_slide(
        presentation.slide_layouts[1]
    )

    slide.shapes.title.text = "Search Agent Sunumu"
    slide.placeholders[1].text = "PPTX indeksleme testi"

    table_shape = slide.shapes.add_table(
        2, 2,
        Inches(1), Inches(3),
        Inches(6), Inches(1)
    )

    table = table_shape.table
    table.cell(0, 0).text = "Proje"
    table.cell(0, 1).text = "Search Agent"
    table.cell(1, 0).text = "Durum"
    table.cell(1, 1).text = "Başarılı"

    presentation.save(file_path)

    db_path = tmp_path / "index.db"

    index_directory(source_dir, db_path)

    with sqlite3.connect(db_path) as connection:
        result = connection.execute(
            """
            SELECT content
            FROM documents
            WHERE file_path = ?
            """,
            (str(file_path.resolve()),)
        ).fetchone()

    assert result is not None
    assert "Search Agent Sunumu" in result[0]
    assert "PPTX indeksleme testi" in result[0]
    assert "Search Agent" in result[0]
    assert "Başarılı" in result[0]

def test_index_directory_indexes_html_files(tmp_path):
    import sqlite3
    from database.document_indexer import index_directory

    source_dir = tmp_path / "documents"
    source_dir.mkdir()

    file_path = source_dir / "rapor.html"

    file_path.write_text(
        """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Search Agent HTML Raporu</title>
            <meta name="description"
                  content="HTML indeksleme açıklaması">
        </head>
        <body>
            <h1>Proje Özeti</h1>
            <p>HTML indeksleme entegrasyon testi.</p>
            <a href="https://example.com/search-agent">
                Proje bağlantısı
            </a>
        </body>
        </html>
        """,
        encoding="utf-8"
    )

    db_path = tmp_path / "index.db"

    index_directory(source_dir, db_path)

    with sqlite3.connect(db_path) as connection:
        result = connection.execute(
            """
            SELECT content
            FROM documents
            WHERE file_path = ?
            """,
            (str(file_path.resolve()),)
        ).fetchone()

    assert result is not None
    assert "Search Agent HTML Raporu" in result[0]
    assert "Proje Özeti" in result[0]
    assert "HTML indeksleme entegrasyon testi" in result[0]
    assert "Proje bağlantısı" in result[0]
    assert "https://example.com/search-agent" in result[0]
    assert "HTML indeksleme açıklaması" in result[0]

import sqlite3
import pytest

from PIL import Image
from database.document_indexer import index_directory


@pytest.mark.parametrize(
    "extension",
    [".png", ".jpg", ".jpeg"]
)
def test_index_directory_indexes_image_files(
    tmp_path,
    monkeypatch,
    extension
):
    source_dir = tmp_path / "documents"
    source_dir.mkdir()

    file_path = source_dir / f"ocr_test{extension}"

    image = Image.new("RGB", (100, 100), "white")
    image.save(file_path)

    def mock_read_file(path):
        return {
            "content": "OCRINDEXTEST SEARCHAGENT IMAGE"
        }

    monkeypatch.setattr(
        "database.document_indexer.read_file",
        mock_read_file
    )

    db_path = tmp_path / "index.db"

    result = index_directory(source_dir, db_path)

    with sqlite3.connect(db_path) as connection:
        document = connection.execute(
            """
            SELECT file_name, file_type, content
            FROM documents
            WHERE file_path = ?
            """,
            (str(file_path.resolve()),)
        ).fetchone()

        search_results = connection.execute(
            """
            SELECT rowid
            FROM document_search
            WHERE document_search MATCH ?
            """,
            ("OCRINDEXTEST",)
        ).fetchall()

    assert result["indexed_count"] == 1
    assert result["error_count"] == 0

    assert document is not None
    assert document[0] == file_path.name
    assert document[1] == extension
    assert "OCRINDEXTEST" in document[2]

    assert len(search_results) == 1


def test_index_directory_reports_image_ocr_errors(
    tmp_path,
    monkeypatch
):
    source_dir = tmp_path / "documents"
    source_dir.mkdir()

    file_path = source_dir / "ocr_error.png"

    image = Image.new("RGB", (100, 100), "white")
    image.save(file_path)

    def mock_read_file(path):
        raise RuntimeError("Tesseract OCR test error")

    monkeypatch.setattr(
        "database.document_indexer.read_file",
        mock_read_file
    )

    db_path = tmp_path / "index.db"

    result = index_directory(source_dir, db_path)

    with sqlite3.connect(db_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]

    assert result["indexed_count"] == 0
    assert result["error_count"] == 1
    assert len(result["errors"]) == 1
    assert "Tesseract OCR test error" in result["errors"][0]["error"]
    assert count == 0

"""
Search Agent - DOCX Reader v0.1

Features:
- Paragraph extraction
- Heading and paragraph style detection
- Table extraction
- Character counting

Original DOCX files are never modified.
"""

from pathlib import Path

from docx import Document


def read_docx(file_path: str | Path) -> dict:
    """Extract paragraphs and tables from a DOCX document."""

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() != ".docx":
        raise ValueError("File must have a DOCX extension.")

    document = Document(path)

    paragraphs = []
    tables = []
    total_characters = 0

    for paragraph in document.paragraphs:
        text = paragraph.text

        if text.strip():
            paragraphs.append({
                "text": text,
                "style": paragraph.style.name,
            })

            total_characters += len(text)

    for table_index, table in enumerate(document.tables, start=1):
        rows = []

        for row in table.rows:
            cells = [cell.text for cell in row.cells]
            rows.append(cells)

            total_characters += sum(len(cell) for cell in cells)

        tables.append({
            "table_number": table_index,
            "rows": rows,
            "row_count": len(rows),
            "column_count": max(
                (len(row) for row in rows),
                default=0
            ),
        })

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_type": "docx",
        "paragraphs": paragraphs,
        "paragraph_count": len(paragraphs),
        "tables": tables,
        "table_count": len(tables),
        "total_characters": total_characters,
    }

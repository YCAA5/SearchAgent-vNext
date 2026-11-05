
"""
Search Agent - Text Reader v0.2

Supported formats:
- TXT
- CSV
- PDF

Features:
- Multiple encoding support
- CSV delimiter detection
- Controlled error handling

Original files are never modified.
"""

import csv

from pathlib import Path
from .docx_reader import read_docx
from .pdf_reader import read_pdf
from .xlsx_reader import read_xlsx
from .pptx_reader import read_pptx
from .html_reader import read_html
from .image_reader import read_image

SUPPORTED_ENCODINGS = [
    "utf-8-sig",
    "cp1254",
    "latin-1",
]


def read_text_content(path: Path) -> str:
    """Read text using supported encodings."""

    for encoding in SUPPORTED_ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError(
        f"Unable to decode file: {path}"
    )


def read_txt(file_path: str | Path) -> dict:
    """Read a TXT file."""

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    content = read_text_content(path)

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_type": "txt",
        "content": content,
        "character_count": len(content),
    }


def read_csv(file_path: str | Path) -> dict:
    """Read a CSV file."""

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    content = read_text_content(path)

    if not content.strip():
        return {
            "file_name": path.name,
            "file_path": str(path.resolve()),
            "file_type": "csv",
            "headers": [],
            "rows": [],
            "row_count": 0,
            "delimiter": None,
        }

    try:
        dialect = csv.Sniffer().sniff(
            content[:8192],
            delimiters=",;\t|"
        )
        delimiter = dialect.delimiter

    except csv.Error:
        delimiter = ","

    reader = csv.DictReader(
        content.splitlines(),
        delimiter=delimiter
    )

    headers = reader.fieldnames or []
    rows = list(reader)

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_type": "csv",
        "headers": headers,
        "rows": rows,
        "row_count": len(rows),
        "delimiter": delimiter,
    }


def read_file(file_path: str | Path) -> dict:
    """Select the appropriate reader."""

    path = Path(file_path)
    extension = path.suffix.lower()

    if extension == ".txt":
        return read_txt(path)

    elif extension == ".csv":
        return read_csv(path)

    elif extension == ".pdf":
        return read_pdf(path)
    
    elif extension == ".docx":
        return read_docx(path)

    elif extension == ".xlsx":
        return read_xlsx(path)
    
    elif extension == ".pptx":
        return read_pptx(path)

    if extension in {".html", ".htm"}:
        return read_html(path)
    if extension in {".png", ".jpg", ".jpeg"}:
        return read_image(path)

    else:
        raise ValueError(f"Unsupported file format: {extension}")
    
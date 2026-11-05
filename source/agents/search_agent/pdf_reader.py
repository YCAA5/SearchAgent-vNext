
"""
Search Agent - PDF Reader v0.2

Features:
- PDF metadata extraction
- Page-by-page text extraction
- OCR for scanned pages
- Empty page detection
- Character counting
- Original PDF files are never modified
"""

import pymupdf

from pathlib import Path

from services.ocr.ocr_reader import read_pil_image_text


def read_pdf(file_path: str | Path) -> dict:
    """Extract text from PDF pages, using OCR when necessary."""

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError("File must have a PDF extension.")

    pages = []
    total_characters = 0
    empty_pages = []
    ocr_pages = []

    with pymupdf.open(path) as document:
        page_count = len(document)

        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").replace("\u00a0", " ")
            extraction_method = "text"

            if not text.strip():
                pixmap = page.get_pixmap(
                    matrix=pymupdf.Matrix(2, 2),
                    alpha=False,
                )

                image = pixmap.pil_image()

                ocr_result = read_pil_image_text(
                    image,
                    languages="tur+eng",
                )

                text = ocr_result["text"]
                extraction_method = "ocr"

                if text.strip():
                    ocr_pages.append(page_number)

            if not text.strip():
                empty_pages.append(page_number)

            total_characters += len(text)

            pages.append({
                "page_number": page_number,
                "text": text,
                "character_count": len(text),
                "extraction_method": extraction_method,
            })

        metadata = document.metadata

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_type": "pdf",
        "page_count": page_count,
        "metadata": metadata,
        "pages": pages,
        "total_characters": total_characters,
        "empty_pages": empty_pages,
        "ocr_pages": ocr_pages,
    }

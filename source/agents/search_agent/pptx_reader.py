
"""
Search Agent - PPTX Reader v0.1

Features:
- Multiple slide extraction
- Slide title extraction
- Text extraction
- Table extraction
- Empty slide detection
- Slide and character counts

Original PPTX files are never modified.
"""

from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


def read_pptx(file_path: str | Path) -> dict:
    """Extract text, titles and tables from a PowerPoint file."""

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() != ".pptx":
        raise ValueError("File must have a PPTX extension.")

    presentation = Presentation(path)

    slides = []
    total_characters = 0
    empty_slides = []

    for slide_number, slide in enumerate(
        presentation.slides,
        start=1
    ):
        title = None
        text_blocks = []
        tables = []

        for shape in slide.shapes:

            # Extract slide title
            if shape.has_text_frame and shape == slide.shapes.title:
                title = shape.text.strip()

            # Extract text
            if shape.has_text_frame:
                text = shape.text.strip()

                if text:
                    text_blocks.append(text)
                    total_characters += len(text)

            # Extract tables
            if shape.has_table:
                table_data = []

                for row in shape.table.rows:
                    row_data = []

                    for cell in row.cells:
                        cell_text = cell.text.strip()
                        row_data.append(cell_text)
                        total_characters += len(cell_text)

                    table_data.append(row_data)

                tables.append(table_data)

        has_content = bool(text_blocks or tables)

        if not has_content:
            empty_slides.append(slide_number)

        slides.append({
            "slide_number": slide_number,
            "title": title,
            "text_blocks": text_blocks,
            "tables": tables,
            "is_empty": not has_content,
        })

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_type": "pptx",
        "slide_count": len(slides),
        "total_characters": total_characters,
        "empty_slides": empty_slides,
        "slides": slides,
    }


"""
Search Agent - Image Reader v0.2

Features:
- PNG, JPG and JPEG support
- Image dimensions and metadata
- EXIF metadata extraction
- Image integrity verification
- OCR text extraction
"""

from pathlib import Path

from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import TAGS

from services.ocr.ocr_reader import read_image_text


SUPPORTED_FORMATS = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
}


def read_image(file_path: str | Path) -> dict:
    """Extract image metadata and OCR text."""

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    extension = path.suffix.lower()

    if extension not in SUPPORTED_FORMATS:
        raise ValueError(
            "Supported formats are PNG, JPG and JPEG."
        )

    try:
        with Image.open(path) as image:
            expected_format = SUPPORTED_FORMATS[extension]

            if image.format != expected_format:
                raise ValueError(
                    f"File extension and image format do not match: "
                    f"{extension} / {image.format}"
                )

            image.verify()

        with Image.open(path) as image:
            exif_data = {}

            exif = image.getexif()

            for tag_id, value in exif.items():
                tag_name = TAGS.get(tag_id, str(tag_id))

                if isinstance(value, bytes):
                    value = value.decode(
                        "utf-8",
                        errors="replace"
                    )

                exif_data[tag_name] = str(value)

            image_metadata = {
                "file_name": path.name,
                "file_path": str(path.resolve()),
                "file_type": "image",
                "format": image.format,
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "file_size_bytes": path.stat().st_size,
                "exif": exif_data,
            }

        # Extract searchable text using OCR.
        ocr_result = read_image_text(
            path,
            languages="tur+eng"
        )

        image_metadata["content"] = ocr_result["text"]
        image_metadata["character_count"] = (
            ocr_result["character_count"]
        )
        image_metadata["ocr"] = {
            "languages": ocr_result["languages"],
            "average_confidence": (
                ocr_result["average_confidence"]
            ),
        }

        return image_metadata

    except UnidentifiedImageError as error:
        raise ValueError(
            f"Invalid or unsupported image file: {path}"
        ) from error


def test_image_reader_includes_ocr_content(tmp_path):
    from PIL import Image, ImageDraw, ImageFont
    from agents.search_agent.text_reader import read_file

    image_path = tmp_path / "search_test.png"

    image = Image.new("RGB", (1600, 300), "white")
    draw = ImageDraw.Draw(image)

    font = ImageFont.truetype(
        r"C:\Windows\Fonts\arial.ttf",
        65
    )

    draw.text(
        (30, 80),
        "SEARCH AGENT OCR TEST",
        fill="black",
        font=font,
    )

    image.save(image_path)

    result = read_file(image_path)

    assert result["file_type"] == "image"
    assert "SEARCH" in result["content"]
    assert "AGENT" in result["content"]
    assert result["character_count"] > 0
    assert result["ocr"]["languages"] == "tur+eng"

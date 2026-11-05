
"""
Search Agent - OCR Service v0.2

Features:
- Local Tesseract OCR
- Turkish and English recognition
- File-based and in-memory image OCR
- OCR confidence calculation
- Original files remain unchanged
"""

from pathlib import Path
from dotenv import load_dotenv

import os
import shutil

import pytesseract
from PIL import Image
from pytesseract import Output

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_environment(
    env_path: str | Path | None = None,
) -> None:
    """Load environment variables from the project .env file."""

    path = (
        Path(env_path)
        if env_path is not None
        else PROJECT_ROOT / ".env"
    )

    load_dotenv(
        dotenv_path=path,
        override=False,
    )


load_environment()

def configure_tesseract() -> str:
    """Find and configure the Tesseract executable."""

    tesseract_path = (
        os.getenv("TESSERACT_CMD")
        or shutil.which("tesseract")
    )

    if not tesseract_path:
        raise RuntimeError(
            "Tesseract OCR bulunamadı. "
            "Lütfen Tesseract'ı kurun veya "
            "TESSERACT_CMD ortam değişkenini tanımlayın."
        )

    pytesseract.pytesseract.tesseract_cmd = tesseract_path

    return tesseract_path

def read_pil_image_text(
    image: Image.Image,
    languages: str = "tur+eng",
) -> dict:
    """Extract text directly from a PIL image."""

    configure_tesseract()

    available_languages = pytesseract.get_languages(config="")

    for language in languages.split("+"):
        if language not in available_languages:
            raise ValueError(
                f"OCR language not installed: {language}"
            )

    with image.convert("RGB") as rgb_image:
        text = pytesseract.image_to_string(
            rgb_image,
            lang=languages,
        )

        data = pytesseract.image_to_data(
            rgb_image,
            lang=languages,
            output_type=Output.DICT,
        )

    confidences = [
        float(value)
        for value in data["conf"]
        if value != "-1"
    ]

    average_confidence = (
        round(sum(confidences) / len(confidences), 2)
        if confidences
        else 0.0
    )

    cleaned_text = text.strip()

    return {
        "languages": languages,
        "text": cleaned_text,
        "character_count": len(cleaned_text),
        "average_confidence": average_confidence,
    }


def read_image_text(
    file_path: str | Path,
    languages: str = "tur+eng",
) -> dict:
    """Extract text from an image file."""

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() not in {
        ".png", ".jpg", ".jpeg"
    }:
        raise ValueError("Unsupported image format.")

    with Image.open(path) as image:
        result = read_pil_image_text(
            image,
            languages=languages,
        )

    result["file_name"] = path.name
    result["file_path"] = str(path.resolve())

    return result

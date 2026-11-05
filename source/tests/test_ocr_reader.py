
import shutil

import pytest

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from services.ocr import ocr_reader
from services.ocr.ocr_reader import read_image_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
@pytest.fixture
def sample_ocr_image(tmp_path):
    image_path = tmp_path / "ocr_test.png"

    image = Image.new("RGB", (1200, 300), "white")
    draw = ImageDraw.Draw(image)

    draw.text(
        (40, 80),
        "SEARCH AGENT TEST 12345",
        fill="black",
    )

    image.save(image_path)

    return image_path


def test_read_image_text(sample_ocr_image):
    result = read_image_text(sample_ocr_image)

    assert result["file_name"] == "ocr_test.png"
    assert result["languages"] == "tur+eng"
    assert isinstance(result["text"], str)


def test_ocr_text_extraction(sample_ocr_image):
    result = read_image_text(sample_ocr_image)

    assert "SEARCH AGENT TEST 12345" in result["text"]


def test_ocr_character_count(sample_ocr_image):
    result = read_image_text(sample_ocr_image)

    assert result["character_count"] == len(result["text"])


def test_ocr_confidence(sample_ocr_image):
    result = read_image_text(sample_ocr_image)

    assert isinstance(result["average_confidence"], float)
    assert 0 <= result["average_confidence"] <= 100


def test_ocr_missing_file():
    with pytest.raises(FileNotFoundError):
        read_image_text("missing_ocr_image.png")


def test_ocr_invalid_extension(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("Test content", encoding="utf-8")

    with pytest.raises(ValueError):
        read_image_text(file_path)


def test_ocr_invalid_language(sample_ocr_image):
    with pytest.raises(ValueError, match="OCR language not installed"):
        read_image_text(sample_ocr_image, languages="invalid")


def test_ocr_turkish_characters(tmp_path):
    image_path = tmp_path / "turkish_test.png"

    image = Image.new("RGB", (1600, 300), "white")
    draw = ImageDraw.Draw(image)

    font_path = (
        PROJECT_ROOT
        / "tests"
        / "assets"
        / "fonts"
        / "NotoSans-Variable.ttf"
    )

    font = ImageFont.truetype(font_path, 65)

    draw.text(
        (30, 80),
        "ÇĞİÖŞÜ çğıöşü Türkçe deneme",
        fill="black",
        font=font,
    )

    draw.text(
        (30, 80),
        "ÇĞİÖŞÜ çğıöşü Türkçe deneme",
        fill="black",
        font=font,
    )

    image.save(image_path)

    result = read_image_text(
        image_path,
        languages="tur"
    )

    assert "Türkçe" in result["text"]
    assert "deneme" in result["text"]
def test_tesseract_uses_environment_variable(monkeypatch):
    custom_path = "/custom/path/tesseract"

    monkeypatch.setenv("TESSERACT_CMD", custom_path)
    monkeypatch.setattr(shutil, "which", lambda _: None)

    result = ocr_reader.configure_tesseract()

    assert result == custom_path
    assert ocr_reader.pytesseract.pytesseract.tesseract_cmd == custom_path


def test_tesseract_uses_system_path(monkeypatch):
    system_path = "/usr/bin/tesseract"

    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr(shutil, "which", lambda _: system_path)

    result = ocr_reader.configure_tesseract()

    assert result == system_path
    assert ocr_reader.pytesseract.pytesseract.tesseract_cmd == system_path


def test_tesseract_not_found(monkeypatch):
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr(shutil, "which", lambda _: None)

    with pytest.raises(RuntimeError, match="Tesseract"):
        ocr_reader.configure_tesseract()

def test_load_environment_reads_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SEARCH_AGENT_TEST_SETTING=loaded_value\n",
        encoding="utf-8",
    )

    monkeypatch.delenv(
        "SEARCH_AGENT_TEST_SETTING",
        raising=False,
    )

    ocr_reader.load_environment(env_file)

    assert (
        __import__("os").getenv("SEARCH_AGENT_TEST_SETTING")
        == "loaded_value"
    )


def test_load_environment_does_not_override_system_variable(
    tmp_path,
    monkeypatch,
):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SEARCH_AGENT_TEST_SETTING=dotenv_value\n",
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "SEARCH_AGENT_TEST_SETTING",
        "system_value",
    )

    ocr_reader.load_environment(env_file)

    assert (
        __import__("os").getenv("SEARCH_AGENT_TEST_SETTING")
        == "system_value"
    )
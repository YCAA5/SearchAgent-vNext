
import pymupdf
import pytest

from agents.search_agent.pdf_reader import read_pdf
from agents.search_agent.text_reader import read_file

@pytest.fixture
def sample_pdf(tmp_path):
    """Create a three-page test PDF."""

    file_path = tmp_path / "test_document.pdf"
    font_path = r"C:\Windows\Fonts\arial.ttf"

    document = pymupdf.open()

    page1 = document.new_page()
    page1.insert_text(
        (72, 100),
        "Search Agent PDF Testi\nTürkçe karakterler: ğ ü ş ı ö ç",
        fontsize=14,
        fontname="TurkishFont",
        fontfile=font_path,
    )

    document.new_page()

    page3 = document.new_page()
    page3.insert_text(
        (72, 100),
        "Third page - PDF text extraction test.",
        fontsize=14,
    )

    document.save(file_path)
    document.close()

    return file_path


def test_read_pdf(sample_pdf):
    result = read_pdf(sample_pdf)

    assert result["file_type"] == "pdf"
    assert result["page_count"] == 3


def test_pdf_page_content(sample_pdf):
    result = read_pdf(sample_pdf)

    assert "Search Agent PDF Testi" in result["pages"][0]["text"]
    assert "Third page" in result["pages"][2]["text"]


def test_turkish_characters(sample_pdf):
    result = read_pdf(sample_pdf)

    assert "ğ ü ş ı ö ç" in result["pages"][0]["text"]


def test_empty_page_detection(sample_pdf):
    result = read_pdf(sample_pdf)

    assert result["empty_pages"] == [2]
    assert result["pages"][1]["character_count"] == 0


def test_character_count(sample_pdf):
    result = read_pdf(sample_pdf)

    expected = sum(
        len(page["text"])
        for page in result["pages"]
    )

    assert result["total_characters"] == expected


def test_missing_pdf():
    with pytest.raises(FileNotFoundError):
        read_pdf("missing_document.pdf")


def test_invalid_extension(tmp_path):
    file_path = tmp_path / "document.txt"
    file_path.write_text("Not a PDF", encoding="utf-8")

    with pytest.raises(ValueError):
        read_pdf(file_path)


def test_corrupted_pdf(tmp_path):
    file_path = tmp_path / "corrupted.pdf"
    file_path.write_bytes(b"This is not a valid PDF")

    with pytest.raises(Exception):
        read_pdf(file_path)

def test_read_file_dispatches_pdf(sample_pdf):
    result = read_file(sample_pdf)

    assert result["file_type"] == "pdf"
    assert result["page_count"] == 3
    assert "Search Agent PDF Testi" in result["pages"][0]["text"]

    
def test_pdf_ocr_extracts_scanned_page(tmp_path):
    from PIL import Image, ImageDraw, ImageFont

    # Create an image containing text.
    image_path = tmp_path / "scanned_page.png"

    image = Image.new("RGB", (1600, 500), "white")
    draw = ImageDraw.Draw(image)

    font = ImageFont.truetype(
        r"C:\Windows\Fonts\arial.ttf",
        80
    )

    draw.text(
        (50, 150),
        "SCANNED PDF TEST",
        fill="black",
        font=font,
    )

    image.save(image_path)

    # Embed the image into a PDF as a scanned page.
    pdf_path = tmp_path / "scanned_document.pdf"

    document = pymupdf.open()
    page = document.new_page(width=800, height=250)

    page.insert_image(
        page.rect,
        filename=str(image_path),
    )

    document.save(pdf_path)
    document.close()

    result = read_pdf(pdf_path)

    assert result["page_count"] == 1
    assert "SCANNED" in result["pages"][0]["text"]
    assert "PDF" in result["pages"][0]["text"]
    assert result["ocr_pages"] == [1]

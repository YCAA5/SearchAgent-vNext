
import zipfile

import pytest
from pptx import Presentation
from pptx.util import Inches

from agents.search_agent.pptx_reader import read_pptx


@pytest.fixture
def sample_pptx(tmp_path):
    """Create a sample PowerPoint with text, tables and empty slides."""

    file_path = tmp_path / "test_presentation.pptx"

    presentation = Presentation()

    # Slide 1: Title and text
    slide1 = presentation.slides.add_slide(
        presentation.slide_layouts[0]
    )

    slide1.shapes.title.text = "Search Agent"

    slide1.placeholders[1].text = (
        "Yapay zeka ile belge arama sistemi"
    )

    # Slide 2: Text and table
    slide2 = presentation.slides.add_slide(
        presentation.slide_layouts[6]
    )

    textbox = slide2.shapes.add_textbox(
        Inches(1), Inches(1), Inches(5), Inches(1)
    )
    textbox.text = "Donanım Listesi"

    table_shape = slide2.shapes.add_table(
        2, 2,
        Inches(1), Inches(2),
        Inches(5), Inches(2)
    )

    table = table_shape.table

    table.cell(0, 0).text = "Ürün"
    table.cell(0, 1).text = "Adet"
    table.cell(1, 0).text = "Ekran Kartı"
    table.cell(1, 1).text = "2"

    # Slide 3: Empty slide
    presentation.slides.add_slide(
        presentation.slide_layouts[6]
    )

    presentation.save(file_path)

    return file_path


def test_read_pptx(sample_pptx):
    result = read_pptx(sample_pptx)

    assert result["file_type"] == "pptx"
    assert result["slide_count"] == 3


def test_slide_titles(sample_pptx):
    result = read_pptx(sample_pptx)

    assert result["slides"][0]["title"] == "Search Agent"


def test_text_extraction(sample_pptx):
    result = read_pptx(sample_pptx)

    slide = result["slides"][0]

    assert (
        "Yapay zeka ile belge arama sistemi"
        in slide["text_blocks"]
    )


def test_turkish_characters(sample_pptx):
    result = read_pptx(sample_pptx)

    slide = result["slides"][0]

    assert any(
        "Yapay zeka" in text
        for text in slide["text_blocks"]
    )


def test_table_extraction(sample_pptx):
    result = read_pptx(sample_pptx)

    slide = result["slides"][1]

    assert len(slide["tables"]) == 1
    assert slide["tables"][0][0] == ["Ürün", "Adet"]
    assert slide["tables"][0][1] == ["Ekran Kartı", "2"]


def test_empty_slide_detection(sample_pptx):
    result = read_pptx(sample_pptx)

    assert result["empty_slides"] == [3]
    assert result["slides"][2]["is_empty"] is True


def test_character_count(sample_pptx):
    result = read_pptx(sample_pptx)

    expected = (
        len("Search Agent")
        + len("Yapay zeka ile belge arama sistemi")
        + len("Donanım Listesi")
        + len("Ürün")
        + len("Adet")
        + len("Ekran Kartı")
        + len("2")
    )

    assert result["total_characters"] == expected


def test_missing_pptx():
    with pytest.raises(FileNotFoundError):
        read_pptx("missing_presentation.pptx")


def test_invalid_extension(tmp_path):
    file_path = tmp_path / "document.txt"

    file_path.write_text(
        "This is not a PowerPoint file.",
        encoding="utf-8"
    )

    with pytest.raises(ValueError):
        read_pptx(file_path)


def test_corrupted_pptx(tmp_path):
    file_path = tmp_path / "corrupted.pptx"

    file_path.write_bytes(
        b"This is not a valid PPTX file."
    )

    with pytest.raises(zipfile.BadZipFile):
        read_pptx(file_path)

def test_read_file_dispatches_pptx(sample_pptx):
    from agents.search_agent.text_reader import read_file

    result = read_file(sample_pptx)

    assert result["file_type"] == "pptx"
    assert result["slide_count"] == 3
    assert result["slides"][0]["title"] == "Search Agent"

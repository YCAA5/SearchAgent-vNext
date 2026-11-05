
import pytest

from PIL import Image

from agents.search_agent.image_reader import read_image


@pytest.fixture
def sample_png(tmp_path):
    image_path = tmp_path / "sample.png"

    image = Image.new("RGB", (800, 600), color="red")
    image.save(image_path, format="PNG")

    return image_path


@pytest.fixture
def sample_jpeg(tmp_path):
    image_path = tmp_path / "sample.jpg"

    image = Image.new("RGB", (1920, 1080), color="blue")
    image.save(image_path, format="JPEG")

    return image_path


def test_read_png(sample_png):
    result = read_image(sample_png)

    assert result["file_name"] == "sample.png"
    assert result["file_type"] == "image"
    assert result["format"] == "PNG"


def test_read_jpeg(sample_jpeg):
    result = read_image(sample_jpeg)

    assert result["format"] == "JPEG"
    assert result["file_type"] == "image"


def test_image_dimensions(sample_png):
    result = read_image(sample_png)

    assert result["width"] == 800
    assert result["height"] == 600


def test_image_color_mode(sample_png):
    result = read_image(sample_png)

    assert result["mode"] == "RGB"


def test_image_file_size(sample_png):
    result = read_image(sample_png)

    assert result["file_size_bytes"] == sample_png.stat().st_size
    assert result["file_size_bytes"] > 0


def test_image_exif_data(sample_jpeg):
    result = read_image(sample_jpeg)

    assert isinstance(result["exif"], dict)


def test_missing_image():
    with pytest.raises(FileNotFoundError):
        read_image("missing_image.png")


def test_invalid_extension(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("This is not an image.")

    with pytest.raises(ValueError):
        read_image(file_path)


def test_corrupted_image(tmp_path):
    file_path = tmp_path / "corrupted.png"
    file_path.write_bytes(b"This is not a valid image.")

    with pytest.raises(ValueError):
        read_image(file_path)


def test_extension_format_mismatch(tmp_path):
    file_path = tmp_path / "wrong_extension.jpg"

    image = Image.new("RGB", (100, 100), color="green")
    image.save(file_path, format="PNG")

    with pytest.raises(ValueError, match="extension and image format"):
        read_image(file_path)

def test_image_exif_extraction(tmp_path):
    file_path = tmp_path / "exif_image.jpg"

    image = Image.new("RGB", (100, 100), color="red")

    exif = Image.Exif()
    exif[274] = 1  # Orientation

    image.save(file_path, format="JPEG", exif=exif)

    result = read_image(file_path)

    assert result["exif"]["Orientation"] == "1"

from agents.search_agent.text_reader import read_file


def test_read_file_dispatches_image(sample_png):
    result = read_file(sample_png)

    assert result["file_type"] == "image"
    assert result["format"] == "PNG"
    assert result["width"] == 800
    assert result["height"] == 600

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
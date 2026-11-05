
import pytest

from agents.search_agent.html_reader import read_html


@pytest.fixture
def sample_html(tmp_path):
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Search Agent Test</title>
        <meta name="description" content="Test açıklaması">
        <meta name="keywords" content="AI, Search, Python">
        <meta name="author" content="Test Author">
        <style>body { color: red; }</style>
        <script>console.log("hidden script");</script>
    </head>
    <body>
        <h1>Ana Başlık</h1>
        <h2>Alt Başlık</h2>
        <p>Bu bir test paragrafıdır.</p>
        <a href="https://example.com">Örnek bağlantı</a>
        <div hidden>Gizli içerik</div>
        <p style="display: none;">Gizli metin</p>
    </body>
    </html>
    """

    file_path = tmp_path / "sample.html"
    file_path.write_text(html_content, encoding="utf-8")

    return file_path


def test_read_html(sample_html):
    result = read_html(sample_html)

    assert result["file_name"] == "sample.html"
    assert result["file_type"] == "html"


def test_html_title(sample_html):
    result = read_html(sample_html)

    assert result["title"] == "Search Agent Test"


def test_html_text_extraction(sample_html):
    result = read_html(sample_html)

    assert "Bu bir test paragrafıdır." in result["text"]
    assert "Ana Başlık" in result["text"]


def test_html_heading_extraction(sample_html):
    result = read_html(sample_html)

    assert len(result["headings"]) == 2
    assert result["headings"][0] == {
        "level": 1,
        "text": "Ana Başlık",
    }
    assert result["headings"][1] == {
        "level": 2,
        "text": "Alt Başlık",
    }


def test_html_link_extraction(sample_html):
    result = read_html(sample_html)

    assert len(result["links"]) == 1
    assert result["links"][0]["text"] == "Örnek bağlantı"
    assert result["links"][0]["url"] == "https://example.com"


def test_html_metadata(sample_html):
    result = read_html(sample_html)

    assert result["metadata"]["description"] == "Test açıklaması"
    assert result["metadata"]["keywords"] == "AI, Search, Python"
    assert result["metadata"]["author"] == "Test Author"


def test_html_hidden_content_excluded(sample_html):
    result = read_html(sample_html)

    assert "hidden script" not in result["text"]
    assert "color: red" not in result["text"]
    assert "Gizli içerik" not in result["text"]
    assert "Gizli metin" not in result["text"]


def test_html_character_count(sample_html):
    result = read_html(sample_html)

    assert result["total_characters"] == len(result["text"])


def test_missing_html():
    with pytest.raises(FileNotFoundError):
        read_html("missing_file.html")


def test_invalid_html_extension(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("Test content", encoding="utf-8")

    with pytest.raises(ValueError):
        read_html(file_path)

from agents.search_agent.text_reader import read_file


def test_read_file_dispatches_html(sample_html):
    result = read_file(sample_html)

    assert result["file_type"] == "html"
    assert result["title"] == "Search Agent Test"
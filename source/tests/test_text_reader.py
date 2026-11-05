
from agents.search_agent.text_reader import read_file


def test_read_txt(tmp_path):
    """TXT dosyası doğru okunmalı."""

    file_path = tmp_path / "test.txt"
    file_path.write_text(
        "Merhaba Dünya!",
        encoding="utf-8"
    )

    result = read_file(file_path)

    assert result["file_type"] == "txt"
    assert result["content"] == "Merhaba Dünya!"
    assert result["character_count"] == 14


def test_read_csv(tmp_path):
    """CSV dosyasındaki başlıklar ve satırlar okunmalı."""

    file_path = tmp_path / "test.csv"
    file_path.write_text(
        "Ad,Şehir\nMurat,İstanbul\n",
        encoding="utf-8"
    )

    result = read_file(file_path)

    assert result["headers"] == ["Ad", "Şehir"]
    assert result["row_count"] == 1
    assert result["rows"][0]["Ad"] == "Murat"


def test_read_semicolon_csv(tmp_path):
    """Noktalı virgüllü CSV algılanmalı."""

    file_path = tmp_path / "test.csv"
    file_path.write_text(
        "Ad;Şehir\nMurat;İstanbul\n",
        encoding="utf-8"
    )

    result = read_file(file_path)

    assert result["delimiter"] == ";"
    assert result["row_count"] == 1


def test_read_empty_csv(tmp_path):
    """Boş CSV hata vermeden okunmalı."""

    file_path = tmp_path / "empty.csv"
    file_path.write_text("", encoding="utf-8")

    result = read_file(file_path)

    assert result["headers"] == []
    assert result["rows"] == []
    assert result["row_count"] == 0


def test_read_cp1254_txt(tmp_path):
    """Windows Türkçe encoding desteklenmeli."""

    file_path = tmp_path / "turkish.txt"
    file_path.write_bytes(
        "Türkçe karakterler: ğ ü ş ı ö ç".encode("cp1254")
    )

    result = read_file(file_path)

    assert "ğ ü ş ı ö ç" in result["content"]


def test_unsupported_format(tmp_path):
    """Desteklenmeyen uzantı kontrollü hata vermeli."""

    file_path = tmp_path / "test.xyz"
    file_path.write_text("Test", encoding="utf-8")

    try:
        read_file(file_path)
        assert False, "ValueError bekleniyordu."

    except ValueError as error:
        assert "Unsupported file format" in str(error)

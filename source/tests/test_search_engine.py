import sqlite3

import pytest

from agents.search_agent.search_engine import search_documents


@pytest.fixture
def search_db(tmp_path):
    db_path = tmp_path / "search_test.db"

    with sqlite3.connect(db_path) as connection:
        connection.executescript("""
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                modified_at TEXT,
                content TEXT NOT NULL,
                indexed_at TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE document_search
            USING fts5(
                file_name,
                content,
                content='documents',
                content_rowid='id'
            );

            CREATE TRIGGER documents_ai AFTER INSERT ON documents BEGIN
                INSERT INTO document_search(rowid, file_name, content)
                VALUES (new.id, new.file_name, new.content);
            END;

            CREATE TRIGGER documents_ad AFTER DELETE ON documents BEGIN
                INSERT INTO document_search(
                    document_search, rowid, file_name, content
                )
                VALUES (
                    'delete', old.id, old.file_name, old.content
                );
            END;

            CREATE TRIGGER documents_au AFTER UPDATE ON documents BEGIN
                INSERT INTO document_search(
                    document_search, rowid, file_name, content
                )
                VALUES (
                    'delete', old.id, old.file_name, old.content
                );

                INSERT INTO document_search(rowid, file_name, content)
                VALUES (new.id, new.file_name, new.content);
            END;
        """)

        documents = [
            (
                "istanbul.txt",
                "C:/Belgeler/istanbul.txt",
                ".txt",
                100,
                "İstanbul Türkiye'nin en büyük şehirlerinden biridir.",
            ),
            (
                "proje.docx",
                "C:/Belgeler/proje.docx",
                ".docx",
                200,
                "Yapay zeka ve makine öğrenmesi üzerine proje çalışması.",
            ),
            (
                "rapor.pdf",
                "C:/Belgeler/rapor.pdf",
                ".pdf",
                300,
                "Yapay zeka teknolojileri ve veri analizi hakkında rapor.",
            ),
            (
                "notlar.txt",
                "C:/Belgeler/notlar.txt",
                ".txt",
                150,
                "Bu belgede yalnızca genel çalışma notları bulunmaktadır.",
            ),
        ]

        for file_name, file_path, file_type, file_size, content in documents:
            connection.execute(
                """
                INSERT INTO documents (
                    file_name,
                    file_path,
                    file_type,
                    file_size,
                    content,
                    indexed_at
                )
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                """,
                (file_name, file_path, file_type, file_size, content),
            )

    return db_path


def test_search_word(search_db):
    result = search_documents(search_db, "teknolojileri")

    assert result["total_count"] == 1
    assert result["results"][0]["file_name"] == "rapor.pdf"


def test_search_multiple_words(search_db):
    result = search_documents(search_db, "yapay zeka")

    assert result["total_count"] == 2


def test_search_exact_phrase(search_db):
    result = search_documents(search_db, '"makine öğrenmesi"')

    assert result["total_count"] == 1
    assert result["results"][0]["file_name"] == "proje.docx"


def test_search_turkish_characters(search_db):
    result = search_documents(search_db, "çalışması")

    assert result["total_count"] == 1
    assert result["results"][0]["file_name"] == "proje.docx"


def test_filter_by_file_type(search_db):
    result = search_documents(
        search_db,
        "yapay zeka",
        file_type=".docx",
    )

    assert result["total_count"] == 1
    assert result["results"][0]["file_name"] == "proje.docx"


def test_filter_by_file_type_without_dot(search_db):
    result = search_documents(
        search_db,
        "yapay zeka",
        file_type="pdf",
    )

    assert result["total_count"] == 1
    assert result["results"][0]["file_name"] == "rapor.pdf"


def test_pagination_limit(search_db):
    result = search_documents(
        search_db,
        "yapay zeka",
        limit=1,
    )

    assert result["total_count"] == 2
    assert len(result["results"]) == 1


def test_pagination_offset(search_db):
    first_page = search_documents(
        search_db,
        "yapay zeka",
        limit=1,
        offset=0,
    )

    second_page = search_documents(
        search_db,
        "yapay zeka",
        limit=1,
        offset=1,
    )

    assert len(first_page["results"]) == 1
    assert len(second_page["results"]) == 1

    assert (
        first_page["results"][0]["id"]
        != second_page["results"][0]["id"]
    )


def test_result_contains_file_information(search_db):
    result = search_documents(search_db, "istanbul")

    document = result["results"][0]

    assert document["file_name"] == "istanbul.txt"
    assert document["file_path"] == "C:/Belgeler/istanbul.txt"
    assert document["file_type"] == ".txt"
    assert document["file_size"] == 100


def test_result_contains_snippet(search_db):
    result = search_documents(search_db, "istanbul")

    snippet = result["results"][0]["snippet"]

    assert "<mark>" in snippet
    assert "</mark>" in snippet


def test_result_contains_relevance(search_db):
    result = search_documents(search_db, "yapay zeka")

    assert "relevance" in result["results"][0]
    assert isinstance(result["results"][0]["relevance"], float)


def test_result_metadata(search_db):
    result = search_documents(
        search_db,
        "istanbul",
        limit=10,
        offset=0,
    )

    assert result["query"] == "istanbul"
    assert result["total_count"] == 1
    assert result["limit"] == 10
    assert result["offset"] == 0


def test_empty_query_raises_error(search_db):
    with pytest.raises(ValueError):
        search_documents(search_db, "")


def test_invalid_limit_raises_error(search_db):
    with pytest.raises(ValueError):
        search_documents(search_db, "istanbul", limit=0)


def test_negative_offset_raises_error(search_db):
    with pytest.raises(ValueError):
        search_documents(search_db, "istanbul", offset=-1)


def test_missing_database_raises_error(tmp_path):
    missing_db = tmp_path / "missing.db"

    with pytest.raises(FileNotFoundError):
        search_documents(missing_db, "istanbul")


def test_database_is_not_modified(search_db):
    with sqlite3.connect(search_db) as connection:
        before = connection.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]

    search_documents(search_db, "istanbul")

    with sqlite3.connect(search_db) as connection:
        after = connection.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]

    assert before == after
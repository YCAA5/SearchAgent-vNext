from contextlib import closing

import sqlite3
import hashlib

from pathlib import Path
from datetime import datetime

from agents.search_agent.file_scanner import scan_directory
from agents.search_agent.text_reader import read_file


def initialize_database(db_path: str | Path) -> None:
    """Create the document index database and its tables."""

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(db_path)) as connection, connection:

        # Main documents table
        connection.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT,
                file_type TEXT,
                file_size INTEGER,
                modified_at TEXT,
                content TEXT,
                indexed_at TEXT
            )
        """)

        # Folder management table
        connection.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_path TEXT NOT NULL UNIQUE,
                folder_name TEXT NOT NULL,
                recursive INTEGER NOT NULL DEFAULT 1,
                is_active INTEGER NOT NULL DEFAULT 1,
                last_scanned_at TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Backward compatibility for existing databases
        columns = connection.execute(
            "PRAGMA table_info(documents)"
        ).fetchall()

        column_names = {column[1] for column in columns}

        if "file_hash" not in column_names:
            connection.execute(
                "ALTER TABLE documents ADD COLUMN file_hash TEXT"
            )

        # Full-text search virtual table
        connection.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS document_search
            USING fts5(
                file_name,
                content,
                content='documents',
                content_rowid='id'
            )
        """)

        # Insert trigger
        connection.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_ai
            AFTER INSERT ON documents
            BEGIN
                INSERT INTO document_search(rowid, file_name, content)
                VALUES (new.id, new.file_name, new.content);
            END
        """)

        # Delete trigger
        connection.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_ad
            AFTER DELETE ON documents
            BEGIN
                INSERT INTO document_search(
                    document_search, rowid, file_name, content
                )
                VALUES (
                    'delete', old.id, old.file_name, old.content
                );
            END
        """)

        # Update trigger
        connection.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_au
            AFTER UPDATE ON documents
            BEGIN
                INSERT INTO document_search(
                    document_search, rowid, file_name, content
                )
                VALUES (
                    'delete', old.id, old.file_name, old.content
                );

                INSERT INTO document_search(rowid, file_name, content)
                VALUES (new.id, new.file_name, new.content);
            END
        """)


def calculate_file_hash(file_path: str | Path) -> str:
    """Calculate SHA-256 hash of a file."""

    sha256 = hashlib.sha256()

    with Path(file_path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def index_document(
    db_path: str | Path,
    document: dict
) -> None:
    """Insert or update a document in the index."""

    initialize_database(db_path)

    file_path = Path(document["file_path"])

    file_hash = (
        calculate_file_hash(file_path)
        if file_path.is_file()
        else None
    )

    with closing(sqlite3.connect(db_path)) as connection, connection:

        existing = connection.execute(
            """
            SELECT file_hash
            FROM documents
            WHERE file_path = ?
            """,
            (document["file_path"],)
        ).fetchone()

        if (
            existing is not None
            and file_hash is not None
            and existing[0] == file_hash
        ):
            return

        connection.execute(
            """
            INSERT INTO documents (
                file_name,
                file_path,
                file_type,
                file_size,
                modified_at,
                content,
                indexed_at,
                file_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(file_path) DO UPDATE SET
                file_name = excluded.file_name,
                file_type = excluded.file_type,
                file_size = excluded.file_size,
                modified_at = excluded.modified_at,
                content = excluded.content,
                indexed_at = excluded.indexed_at,
                file_hash = excluded.file_hash
            """,
            (
                document["file_name"],
                document["file_path"],
                document["file_type"],
                document["file_size"],
                document.get("modified_at"),
                document["content"],
                datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
                file_hash,
            )
        )


def _extract_text(value) -> str:
    """Convert nested reader output into searchable text."""

    ignored_keys = {
        "file_name",
        "file_path",
        "file_type",
        "modified_at",
        "character_count",
        "paragraph_count",
        "table_count",
        "total_characters",
        "page_count",
        "slide_count",
        "sheet_count",
        "row_count",
        "delimiter",
        "empty_pages",
        "empty_slides",
        "ocr_pages",
    }

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        parts = []

        for key, item in value.items():
            if isinstance(key, str) and key.lower() in ignored_keys:
                continue

            extracted = _extract_text(item)

            if extracted:
                parts.append(extracted)

        return "\n".join(parts)

    if isinstance(value, (list, tuple)):
        parts = [
            _extract_text(item)
            for item in value
        ]

        return "\n".join(
            part for part in parts if part
        )

    return ""


def index_directory(
    root_path: str | Path,
    db_path: str | Path
) -> dict:
    """Scan a directory and index supported documents."""

    root_path = Path(root_path)

    initialize_database(db_path)

    scan_result = scan_directory(root_path)

    indexed_count = 0
    errors = []

    supported_extensions = {
        ".txt",
        ".csv",
        ".docx",
        ".pdf",
        ".xlsx",
        ".pptx",
        ".html",
        ".htm",
        ".png",
        ".jpg",
        ".jpeg",
    }

    for file_info in scan_result.get("supported_files", []):

        file_path = Path(file_info["path"])

        if file_path.suffix.lower() not in supported_extensions:
            continue

        try:
            reader_result = read_file(file_path)

            content = _extract_text(reader_result)

            document = {
                "file_name": file_info["name"],
                "file_path": str(file_path.resolve()),
                "file_type": file_path.suffix.lower(),
                "file_size": file_info["size_bytes"],
                "modified_at": file_info["modified_at"],
                "content": content,
            }

            index_document(db_path, document)
            indexed_count += 1

        except Exception as error:
            errors.append({
                "file_path": str(file_path),
                "error": str(error),
            })

    return {
        "indexed_count": indexed_count,
        "error_count": len(errors),
        "errors": errors,
    }

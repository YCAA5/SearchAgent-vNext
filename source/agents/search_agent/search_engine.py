from contextlib import closing
import re
import sqlite3
from pathlib import Path


def _build_fts_query(query: str) -> str:
    """Convert plain words and quoted phrases into a safe FTS5 query."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Arama sorgusu boş olamaz.")

    parts = re.findall(r'"((?:[^"]|"")*)"|(\S+)', query.strip())
    terms = []

    for phrase, word in parts:
        value = phrase.replace('""', '"') if phrase else word

        if value.strip():
            escaped = value.replace('"', '""')
            terms.append(f'"{escaped}"')

    if not terms:
        raise ValueError("Aranabilir bir ifade bulunamadı.")

    return " AND ".join(terms)


def search_documents(
    db_path,
    query: str,
    file_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """
    Search indexed documents using SQLite FTS5.

    Unquoted words are combined with AND.
    Text inside double quotes is treated as an exact phrase.

    Results are ordered by BM25 relevance.
    The database is accessed in query-only mode.
    """

    db_path = Path(db_path)

    if not db_path.is_file():
        raise FileNotFoundError(f"Veritabanı bulunamadı: {db_path}")

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit en az 1 olan bir tam sayı olmalıdır.")

    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ValueError("offset negatif olmayan bir tam sayı olmalıdır.")

    fts_query = _build_fts_query(query)

    conditions = ["document_search MATCH ?"]
    parameters = [fts_query]

    if file_type:
        extension = file_type.strip().lower()

        if not extension:
            raise ValueError("Dosya türü boş olamaz.")

        if not extension.startswith("."):
            extension = f".{extension}"

        conditions.append("LOWER(documents.file_type) IN (?, ?)")
        parameters.extend([extension, extension[1:]])

    where_clause = " AND ".join(conditions)

    count_sql = f"""
        SELECT COUNT(*)
        FROM document_search
        JOIN documents
            ON document_search.rowid = documents.id
        WHERE {where_clause}
    """

    search_sql = f"""
        SELECT
            documents.id,
            documents.file_name,
            documents.file_path,
            documents.file_type,
            documents.file_size,
            documents.modified_at,
            documents.indexed_at,
            snippet(
                document_search,
                1,
                '<mark>',
                '</mark>',
                '...',
                12
            ) AS snippet,
            bm25(document_search) AS relevance
        FROM document_search
        JOIN documents
            ON document_search.rowid = documents.id
        WHERE {where_clause}
        ORDER BY relevance ASC
        LIMIT ? OFFSET ?
    """

    try:
        with closing(sqlite3.connect(db_path)) as connection, connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")

            total_count = connection.execute(
                count_sql,
                parameters,
            ).fetchone()[0]

            rows = connection.execute(
                search_sql,
                parameters + [limit, offset],
            ).fetchall()

            results = [dict(row) for row in rows]

    except sqlite3.OperationalError as exc:
        raise ValueError(
            f"Arama sorgusu çalıştırılamadı: {exc}"
        ) from exc

    return {
        "query": query,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "results": results,
    }

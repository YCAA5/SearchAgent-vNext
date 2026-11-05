"""Small persistent index metadata and bounded immutable snapshot keys."""
import hashlib
import os
import time
import json
import sqlite3
from contextlib import closing
from pathlib import Path


def fingerprint(document):
    value = json.dumps([document['file_path'], document['file_name'], document['file_type'], document['content']], ensure_ascii=False)
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def file_token(path):
    path = Path(path)
    result = [str(path.absolute())]
    for item in (path, Path(str(path) + '-wal')):
        try:
            stat = item.stat()
            result.append((stat.st_mtime_ns, stat.st_size, stat.st_ino))
        except FileNotFoundError:
            result.append(None)
    return tuple(result)


def metadata(path):
    if not Path(path).is_file():
        return {}
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        try:
            return dict(connection.execute('SELECT key,value FROM catalog_meta'))
        except sqlite3.OperationalError:
            return {}


def initialize(connection):
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS catalog_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS content_fingerprints(file_path TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS scan_roots(root TEXT PRIMARY KEY, identity TEXT, available INTEGER NOT NULL);
    INSERT OR IGNORE INTO catalog_meta VALUES('dirty','1');
    INSERT OR IGNORE INTO catalog_meta VALUES('revision','legacy');
    CREATE TRIGGER IF NOT EXISTS catalog_dirty_insert AFTER INSERT ON documents BEGIN
        UPDATE catalog_meta SET value='1' WHERE key='dirty';
    END;
    CREATE TRIGGER IF NOT EXISTS catalog_dirty_update AFTER UPDATE ON documents BEGIN
        UPDATE catalog_meta SET value='1' WHERE key='dirty';
    END;
    CREATE TRIGGER IF NOT EXISTS catalog_dirty_delete AFTER DELETE ON documents BEGIN
        UPDATE catalog_meta SET value='1' WHERE key='dirty';
    END;
    """)


def replace_index(source, target):
    for attempt in range(40):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(0.05)

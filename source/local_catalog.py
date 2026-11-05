import os
import json
import time
import uuid
import hashlib
import threading
import catalog_state
from scope_paths import normalize_roots, path_key, within, volume_identity
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from functools import lru_cache

import pymupdf

from agents.search_agent.search_engine import search_documents
from database.document_indexer import _extract_text, initialize_database
from agents.search_agent.text_reader import read_file
from format_readers import EXTRA_EXTENSIONS, IMAGE_EXTENSIONS, read_extended, read_image_text
from app_paths import APP_ROOT, DATA_ROOT


CONTENT_EXTENSIONS = {'.txt', '.csv', '.pdf', '.docx', '.xlsx', '.pptx', '.html', '.htm'} | EXTRA_EXTENSIONS
EXCLUDED_DIRECTORIES = {'.git', '.venv', 'venv', '.runtime', '__pycache__', '.pytest_cache', 'node_modules', '$recycle.bin', 'system volume information'}
MAX_CONTENT_BYTES = 50 * 1024 * 1024
PROJECT_ROOT = APP_ROOT
DELIVERY_ROOT = APP_ROOT.parent if APP_ROOT.name == 'source' else (APP_ROOT.parent.parent if APP_ROOT.parent.name == 'application' else None)
INTERNAL_OUTPUTS = tuple(DELIVERY_ROOT / name for name in ('validation', 'reports', 'build', 'application', 'releases')) if DELIVERY_ROOT else ()


def extract_content(path, ocr=False):
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        return read_image_text(path) if ocr else ''
    if path.suffix.lower() in EXTRA_EXTENSIONS:
        return read_extended(path)
    if path.suffix.lower() == '.pdf':
        with pymupdf.open(path) as document:
            return '\n'.join(page.get_text('text') for page in document).strip()
    return _extract_text(read_file(path))


def is_link(path):
    return path.is_symlink() or path.is_junction()


@lru_cache(maxsize=4096)
def is_generated_directory(directory):
    directory = Path(directory)
    if directory.is_relative_to(PROJECT_ROOT / 'logs') or directory.is_relative_to(DATA_ROOT / 'logs'):
        return True
    for parent in (directory, *directory.parents):
        if parent.name.lower() == 'library' and (parent.parent / 'Assets').is_dir() and (parent.parent / 'ProjectSettings').is_dir():
            return True
        if parent.name.lower() in {'obj', 'bin'} and any(parent.parent.glob('*.csproj')):
            return True
    return False


def rebuild_catalog(roots, db_path, progress=None, cancel=None, ocr=False):
    started = time.perf_counter()
    roots = normalize_roots(roots)
    if not roots:
        raise ValueError('En az bir klasör seçin.')
    db_path = Path(db_path).absolute()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='catalog-', suffix='.db', dir=db_path.parent)
    os.close(descriptor)
    temporary = Path(temporary)
    report = {'indexed': 0, 'content': 0, 'name_only': 0, 'errors': [], 'reused': 0,
              'generated_name_only': 0, 'formats': {}, 'updated': 0, 'removed': 0,
              'preserved': 0, 'unavailable_roots': [], 'read_s': 0.0}
    cancel = cancel or threading.Event()
    seen = set()
    failed = []
    previous = {}
    is_generated_directory.cache_clear()
    try:
        if db_path.is_file():
            with closing(sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True)) as old:
                with closing(sqlite3.connect(temporary)) as target:
                    old.backup(target)
        initialize_database(temporary)
        with closing(sqlite3.connect(temporary)) as connection:
            connection.row_factory = sqlite3.Row
            catalog_state.initialize(connection)
            old_meta = dict(connection.execute('SELECT key,value FROM catalog_meta'))
            old_volumes = {row['root']: row['identity'] for row in connection.execute('SELECT * FROM scan_roots')}
            previous = {path_key(row['file_path']): dict(row) for row in connection.execute(
                'SELECT id,file_path,file_size,modified_at,length(content)>0 AS has_content FROM documents')}
            # Migrate legacy catalogs once. Future updates hash changed contents only.
            if old_meta.get('dirty') != '0':
                connection.execute('DELETE FROM content_fingerprints')
                for row in connection.execute("SELECT file_path,file_name,file_type,content FROM documents WHERE length(trim(content))>0").fetchall():
                    connection.execute('INSERT INTO content_fingerprints VALUES (?,?)', (row['file_path'], catalog_state.fingerprint(row)))
            connection.commit()
            with connection:
                connection.execute('DELETE FROM scan_roots')
                for root in roots:
                    if cancel.is_set():
                        raise InterruptedError('Tarama durduruldu; önceki dizin korundu.')
                    identity = volume_identity(root)
                    volume_changed = identity is not None and old_volumes.get(path_key(root)) not in {None, identity}
                    try:
                        available = root.is_dir() and not is_link(root)
                    except OSError:
                        available = False
                    if not available:
                        failed.append(root)
                        report['unavailable_roots'].append(str(root))
                        report['errors'].append(f'{root}: Konum çevrimdışı veya erişilemiyor; önceki kayıtlar korundu.')
                        connection.execute('INSERT INTO scan_roots VALUES (?,?,0)', (path_key(root), old_volumes.get(path_key(root))))
                        continue
                    def record_error(error):
                        failed.append(Path(error.filename) if getattr(error, 'filename', None) else root)
                        report['errors'].append(str(error))
                        if str(root) not in report['unavailable_roots']:
                            report['unavailable_roots'].append(str(root))
                    for directory, folders, filenames in os.walk(root, followlinks=False, onerror=record_error):
                        if cancel.is_set():
                            raise InterruptedError('Tarama durduruldu; önceki dizin korundu.')
                        folders[:] = [name for name in folders if name.lower() not in EXCLUDED_DIRECTORIES
                                      and (Path(directory) / name).absolute() not in INTERNAL_OUTPUTS
                                      and not is_link(Path(directory) / name)
                                      and (Path(directory) / name).absolute() != db_path.parent
                                      and not (Path(directory) / name / 'SearchAgent.exe').is_file()
                                      and not (Path(directory) / name / 'Analysis-00.toc').is_file()]
                        for filename in filenames:
                            if cancel.is_set():
                                raise InterruptedError('Tarama durduruldu; önceki dizin korundu.')
                            path = Path(directory) / filename
                            key = path_key(path)
                            if key in seen or path in {db_path, temporary} or is_link(path):
                                continue
                            seen.add(key)
                            try:
                                stat = path.stat()
                                modified = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat()
                                extension = path.suffix.lower()
                                supported = extension in CONTENT_EXTENSIONS or ocr and extension in IMAGE_EXTENSIONS
                                generated = supported and is_generated_directory(path.parent) and not is_generated_directory(root)
                                if generated:
                                    report['generated_name_only'] += 1
                                old = previous.get(key)
                                cache_valid = (old and old['file_path'] == str(path) and not volume_changed and
                                               (old['file_size'], old['modified_at']) == (stat.st_size, modified) and
                                               (extension not in IMAGE_EXTENSIONS or old_meta.get('ocr', str(bool(ocr))) == str(bool(ocr))) and
                                               bool(old['has_content']) == bool(supported and not generated))
                                if cache_valid:
                                    report['reused'] += int(bool(old['has_content']))
                                    continue
                                content = ''
                                if supported and not generated and stat.st_size <= MAX_CONTENT_BYTES:
                                    tick = time.perf_counter()
                                    try:
                                        content = extract_content(path, ocr=True) if ocr else extract_content(path)
                                        if extension == '.pdf' and not content:
                                            report['errors'].append(f'{path}: PDF metin katmanı yok; yalnızca adı eklendi.')
                                    except OSError as error:
                                        if old:
                                            failed.append(path)
                                            report['errors'].append(f'{path}: İçerik erişilemiyor; önceki kayıt korundu: {error}')
                                            continue
                                        report['errors'].append(f'{path}: İçerik okunamadı, yalnızca adı eklendi: {error}')
                                    except Exception as error:
                                        report['errors'].append(f'{path}: İçerik okunamadı, yalnızca adı eklendi: {error}')
                                    report['read_s'] += time.perf_counter() - tick
                                if old and old['file_path'] != str(path):
                                    connection.execute('DELETE FROM documents WHERE file_path=?', (old['file_path'],))
                                    connection.execute('DELETE FROM content_fingerprints WHERE file_path=?', (old['file_path'],))
                                connection.execute(
                                    """INSERT INTO documents(file_name,file_path,file_type,file_size,modified_at,content,indexed_at)
                                       VALUES(?,?,?,?,?,?,?) ON CONFLICT(file_path) DO UPDATE SET
                                       file_name=excluded.file_name,file_type=excluded.file_type,file_size=excluded.file_size,
                                       modified_at=excluded.modified_at,content=excluded.content,indexed_at=excluded.indexed_at""",
                                    (path.name, str(path), extension, stat.st_size, modified, content,
                                     datetime.now().astimezone().isoformat()))
                                if content.strip():
                                    doc = {'file_path': str(path), 'file_name': path.name, 'file_type': extension, 'content': content}
                                    connection.execute('INSERT OR REPLACE INTO content_fingerprints VALUES (?,?)',
                                                       (str(path), catalog_state.fingerprint(doc)))
                                else:
                                    connection.execute('DELETE FROM content_fingerprints WHERE file_path=?', (str(path),))
                                report['updated'] += 1
                            except OSError as error:
                                failed.append(path)
                                report['errors'].append(str(error))
                            finally:
                                if progress and len(seen) % 25 == 0:
                                    progress(len(seen), str(path))
                    # A share can disappear after its root check. Preserve unseen records conservatively.
                    if not root.is_dir():
                        failed.append(root)
                        report['unavailable_roots'].append(str(root))
                    connection.execute('INSERT INTO scan_roots VALUES (?,?,?)',
                                       (path_key(root), identity or old_volumes.get(path_key(root)), int(root not in failed)))
                for key, old in previous.items():
                    if key in seen:
                        continue
                    selected = any(within(old['file_path'], root) for root in roots)
                    if selected and any(within(old['file_path'], root) for root in failed):
                        report['preserved'] += 1
                        continue
                    connection.execute('DELETE FROM documents WHERE file_path=?', (old['file_path'],))
                    connection.execute('DELETE FROM content_fingerprints WHERE file_path=?', (old['file_path'],))
                    report['removed'] += 1
                if cancel.is_set():
                    raise InterruptedError('Tarama durduruldu; önceki dizin korundu.')
                files, count = connection.execute("SELECT count(*),coalesce(sum(length(trim(content))>0),0) FROM documents").fetchone()
                report.update(indexed=files, content=count, name_only=files-count)
                report['formats'] = dict(connection.execute("SELECT file_type,count(*) FROM documents WHERE length(trim(content))>0 GROUP BY file_type"))
                if files == 0 and report['errors'] and report['unavailable_roots']:
                    raise ValueError('Klasörler okunamadı; önceki dizin korundu. ' + report['errors'][0])
                digest = hashlib.sha256(''.join(row[0] for row in connection.execute(
                    'SELECT fingerprint FROM content_fingerprints ORDER BY file_path')).encode('ascii')).hexdigest()
                values = {'signature': digest, 'dirty': '0', 'revision': uuid.uuid4().hex,
                          'roots': json.dumps(sorted(path_key(root) for root in roots)), 'ocr': str(bool(ocr)),
                          'unavailable_roots': json.dumps(report['unavailable_roots']),
                          'files': str(files), 'content': str(count)}
                connection.executemany('INSERT OR REPLACE INTO catalog_meta VALUES (?,?)', values.items())
        catalog_state.replace_index(temporary, db_path)
        report['elapsed_s'] = time.perf_counter() - started
        return report
    finally:
        temporary.unlink(missing_ok=True)


def search_catalog(db_path, query, mode='İçerik ve ad', extension='', limit=200):
    if not query.strip():
        raise ValueError('Aranacak kelimeyi yazın.')
    if not Path(db_path).is_file():
        raise ValueError('Önce seçili klasörleri tarayın.')
    if mode != 'Dosya adı':
        return search_documents(db_path, query, file_type=extension or None, limit=limit)
    escaped = query.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.create_function('casefold', 1, lambda value: value.casefold())
        conditions = "casefold(file_name) LIKE casefold(?) ESCAPE '\\'"
        parameters = [f'%{escaped}%']
        if extension.strip():
            conditions += ' AND file_type = ?'
            parameters.append('.' + extension.strip().lower().lstrip('.'))
        count = connection.execute(f'SELECT COUNT(*) FROM documents WHERE {conditions}', parameters).fetchone()[0]
        rows = connection.execute(
            f"SELECT file_name, file_path, file_type, '' AS snippet FROM documents WHERE {conditions} ORDER BY file_name LIMIT ?",
            parameters + [limit],
        ).fetchall()
    return {'total_count': count, 'results': [dict(row) for row in rows]}

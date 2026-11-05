import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from collections import OrderedDict
from contextlib import closing
from pathlib import Path

import numpy as np

from catalog_state import file_token, replace_index, metadata as catalog_metadata
from model_runtime import LocalEmbedder, MODEL

RECIPE = 'qwen-chars2200-overlap250-name-v1'
QUERY_INSTRUCTION = 'Instruct: Given remembered contents or a summary of a document, retrieve passages describing the same subject, situation and details, even when different words are used.\nQuery: '

_CACHE = OrderedDict()
_QUERY_CACHE = OrderedDict()
_CACHE_LOCK = threading.RLock()


def description_parts(query):
    query = query.strip()
    if len(query) <= 240:
        return [query]
    parts = [part.strip() for part in re.split(r'(?<=[.!?;])\s+|\n+', query) if len(part.strip()) >= 30]
    if len(parts) < 2 or any(len(part) > 2200 for part in parts):
        parts = [chunk for start, chunk in split_chunks(query, size=1800, overlap=180)]
    if len(parts) > 4:
        parts = [parts[position] for position in np.linspace(0, len(parts) - 1, 4, dtype=int)]
    return list(dict.fromkeys([query[:2200]] + parts))


def index_coverage(catalog_path):
    if not Path(catalog_path).is_file():
        return {'files': 0, 'content': 0}
    meta = catalog_metadata(catalog_path)
    if meta.get('dirty') == '0' and 'files' in meta:
        return {'files': int(meta['files']), 'content': int(meta['content'])}
    with closing(sqlite3.connect(Path(catalog_path).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        files, content = connection.execute("SELECT count(*), coalesce(sum(length(trim(content)) > 0), 0) FROM documents").fetchone()
    return {'files': files, 'content': content}


def read_documents(db_path):
    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(
            "SELECT file_path, file_name, file_type, content FROM documents WHERE length(trim(content)) > 0 ORDER BY file_path")]


def fingerprint(document):
    value = json.dumps([document['file_path'], document['file_name'], document['file_type'], document['content']], ensure_ascii=False)
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def catalog_signature(documents):
    return hashlib.sha256(''.join(fingerprint(document) for document in documents).encode('ascii')).hexdigest()


def signature(path):
    meta = catalog_metadata(path)
    return meta['signature'] if meta.get('dirty') == '0' and 'signature' in meta else catalog_signature(read_documents(path))


def split_chunks(text, size=2200, overlap=250):
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(' ', start + size // 2, end)
            if boundary > start:
                end = boundary
        chunk = text[start:end]
        if chunk.strip():
            yield start, chunk
        if end == len(text):
            break
        start = max(start + 1, end - overlap)


def normalized_vectors(values):
    vectors = np.asarray(values, dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[1] != 1024 or not np.isfinite(vectors).all():
        raise RuntimeError('Model geçersiz veya uyumsuz vektör döndürdü.')
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if (norms <= 0).any():
        raise RuntimeError('Model boş vektör döndürdü.')
    return vectors / norms


def initialize_semantic(connection):
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS indexed_documents (file_path TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS chunks (
            file_path TEXT NOT NULL, start INTEGER NOT NULL, content TEXT NOT NULL,
            vector BLOB NOT NULL, PRIMARY KEY (file_path, start));
    ''')


def _ready(path):
    if not Path(path).is_file():
        return False
    with closing(sqlite3.connect(path)) as connection:
        try:
            return dict(connection.execute('SELECT key,value FROM metadata')).get('ready') == '1'
        except sqlite3.Error:
            return False


def build_semantic_index(catalog_path, semantic_path, progress=None, cancel=None, embedder=None):
    started = time.perf_counter()
    cancel = cancel or threading.Event()
    embedder = embedder or LocalEmbedder()
    digest = embedder.ensure_ready()
    catalog_path, semantic_path = Path(catalog_path), Path(semantic_path)
    catalog_token = file_token(catalog_path)
    wanted_signature = signature(catalog_path)
    meta = catalog_metadata(catalog_path)
    if meta.get('dirty') == '0':
        with closing(sqlite3.connect(catalog_path)) as catalog:
            catalog.row_factory = sqlite3.Row
            documents = [dict(row) for row in catalog.execute(
                '''SELECT d.file_path,d.file_name,d.file_type,f.fingerprint
                   FROM documents d JOIN content_fingerprints f ON d.file_path=f.file_path
                   ORDER BY d.file_path''')]
    else:
        documents = read_documents(catalog_path)
        for doc in documents:
            doc['fingerprint'] = fingerprint(doc)
    if not documents:
        raise ValueError('İçeriği okunabilen dosya yok. Önce dosya dizinini oluşturun.')
    semantic_path.parent.mkdir(parents=True, exist_ok=True)
    # Preserve the last ready index while building/resuming its replacement.
    work_path = Path(str(semantic_path) + '.pending') if _ready(semantic_path) else semantic_path
    if work_path != semantic_path and not work_path.is_file():
        with closing(sqlite3.connect(semantic_path)) as original, closing(sqlite3.connect(work_path)) as copy:
            original.backup(copy)
    identity = f'{MODEL}:{digest}:{RECIPE}'
    batch_size = max(1, min(32, int(os.environ.get('SEARCH_AGENT_BATCH_SIZE', '8'))))
    indexed = cached = 0
    embedding_s = 0
    with closing(sqlite3.connect(work_path)) as connection, closing(sqlite3.connect(catalog_path)) as catalog:
        initialize_semantic(connection)
        previous_meta = dict(connection.execute('SELECT key,value FROM metadata'))
        with connection:
            if previous_meta.get('identity') != identity:
                connection.execute('DELETE FROM indexed_documents')
                connection.execute('DELETE FROM chunks')
            connection.executemany('INSERT OR REPLACE INTO metadata VALUES (?,?)', [('identity', identity), ('ready', '0')])
        existing = dict(connection.execute('SELECT file_path,fingerprint FROM indexed_documents'))
        changed = []
        for document in documents:
            if existing.get(document['file_path']) == document['fingerprint']:
                cached += 1
            else:
                changed.append(document)
        def tasks():
            nonlocal cached
            for document in changed:
                if cancel.is_set():
                    raise InterruptedError('Anlam dizini hazırlığı durduruldu. Tekrar başlatıldığında kaldığı yerden devam eder.')
                path = document['file_path']
                text = document.get('content')
                if text is None:
                    text = catalog.execute('SELECT content FROM documents WHERE file_path=?', (path,)).fetchone()[0]
                chunks = list(split_chunks(text))
                with connection:
                    connection.execute('DELETE FROM chunks WHERE file_path=?', (path,))
                    connection.execute('DELETE FROM indexed_documents WHERE file_path=?', (path,))
                for position, (start, chunk) in enumerate(chunks):
                    yield document, start, chunk, position == len(chunks)-1
        iterator = iter(tasks())
        while True:
            if cancel.is_set():
                raise InterruptedError('Anlam dizini hazırlığı durduruldu. Tekrar başlatıldığında kaldığı yerden devam eder.')
            batch = []
            for _ in range(batch_size):
                try:
                    batch.append(next(iterator))
                except StopIteration:
                    break
            if not batch:
                break
            tick = time.perf_counter()
            vectors = normalized_vectors(embedder.embed([doc['file_name'] + '\n' + text for doc, start, text, last in batch]))
            embedding_s += time.perf_counter() - tick
            completed = []
            with connection:
                for (document, start, text, last), vector in zip(batch, vectors, strict=True):
                    connection.execute('INSERT INTO chunks VALUES (?,?,?,?)', (document['file_path'], start, text, vector.tobytes()))
                    if last:
                        connection.execute('INSERT OR REPLACE INTO indexed_documents VALUES (?,?)',
                                           (document['file_path'], document['fingerprint']))
                        indexed += 1
                        completed.append(document['file_name'])
            if progress:
                progress(indexed + cached, len(documents), completed[-1] if completed else batch[-1][0]['file_name'])
        if cancel.is_set():
            raise InterruptedError('Anlam dizini hazırlığı durduruldu.')
        if file_token(catalog_path) != catalog_token:
            raise ValueError('Dosya dizini hazırlık sırasında değişti. Anlam dizinini yeniden hazırlayın.')
        valid_paths = {document['file_path'] for document in documents}
        with connection:
            for path, in connection.execute('SELECT file_path FROM indexed_documents').fetchall():
                if path not in valid_paths:
                    connection.execute('DELETE FROM chunks WHERE file_path=?', (path,))
                    connection.execute('DELETE FROM indexed_documents WHERE file_path=?', (path,))
            connection.executemany('INSERT OR REPLACE INTO metadata VALUES (?,?)',
                                   [('signature', wanted_signature), ('ready', '1')])
        chunk_count = connection.execute('SELECT count(*) FROM chunks').fetchone()[0]
    if work_path != semantic_path:
        replace_index(work_path, semantic_path)
    return {'documents': len(documents), 'chunks': chunk_count, 'updated': indexed, 'cached': cached,
            'elapsed_s': time.perf_counter()-started, 'embedding_s': embedding_s, 'batch_size': batch_size}


def snapshot(catalog_path, semantic_path):
    key = (file_token(catalog_path), file_token(semantic_path))
    with _CACHE_LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
        current_signature = signature(catalog_path)
        with closing(sqlite3.connect(Path(catalog_path).resolve().as_uri()+'?mode=ro', uri=True)) as catalog:
            catalog.row_factory = sqlite3.Row
            documents = {row['file_path']: dict(row) for row in catalog.execute(
                "SELECT file_path,file_name,file_type FROM documents WHERE length(trim(content))>0")}
        with closing(sqlite3.connect(Path(semantic_path).resolve().as_uri()+'?mode=ro', uri=True)) as connection:
            meta = dict(connection.execute('SELECT key,value FROM metadata'))
            chunks = connection.execute('SELECT file_path,start,content,vector FROM chunks').fetchall()
        matrix = np.stack([np.frombuffer(chunk[3], dtype=np.float32) for chunk in chunks]) if chunks else np.empty((0,1024), dtype=np.float32)
        matrix.flags.writeable = False
        grouped = {}
        for position, chunk in enumerate(chunks):
            if chunk[0] in documents:
                grouped.setdefault(chunk[0], []).append(position)
        view = {'documents': documents, 'meta': meta, 'chunks': chunks, 'matrix': matrix, 'grouped': grouped,
                'stale': meta.get('signature') != current_signature}
        # Never cache a snapshot read across an atomic replacement.
        if key != (file_token(catalog_path), file_token(semantic_path)):
            return snapshot(catalog_path, semantic_path)
        _CACHE[key] = view
        while len(_CACHE) > 2:
            _CACHE.popitem(last=False)
        return view


def semantic_search(catalog_path, semantic_path, query, extension='', limit=30, embedder=None, *, allow_stale=False, roots=None):
    started = time.perf_counter()
    if not query.strip():
        raise ValueError('Aradığınız dosyayı birkaç kelime veya cümleyle betimleyin.')
    if len(query) > 6000:
        raise ValueError('Betimlemeyi 6000 karakterden kısa tutun.')
    if not Path(semantic_path).is_file():
        raise ValueError('Önce “Anlam dizinini hazırla” düğmesine basın.')
    embedder = embedder or LocalEmbedder()
    digest = embedder.ensure_ready()
    view = snapshot(catalog_path, semantic_path)
    loaded = time.perf_counter()
    if view['meta'].get('ready') != '1' or view['stale'] and not allow_stale:
        raise ValueError('Dosya dizini değişmiş veya anlam dizini tamamlanmamış. Anlam dizinini hazırlayın.')
    identity = f'{MODEL}:{digest}:{RECIPE}'
    if view['meta'].get('identity') != identity:
        raise ValueError('Model değişmiş. Anlam dizinini yeniden hazırlayın.')
    wanted_type = '.' + extension.strip().lower().lstrip('.') if extension.strip() else ''
    grouped = view['grouped']
    if roots is not None:
        from scope_paths import normalize_roots, within
        scopes = normalize_roots(roots)
        grouped = {p: positions for p, positions in grouped.items() if any(within(p, scope) for scope in scopes)}
    if wanted_type:
        grouped = {p: positions for p,positions in grouped.items() if view['documents'][p]['file_type'] == wanted_type}
    if not grouped:
        return {'total_count': 0, 'results': [], 'stale': view['stale']}
    parts = description_parts(query)
    query_key = (identity, tuple(parts))
    real_model = type(embedder) is LocalEmbedder
    with _CACHE_LOCK:
        query_vectors = _QUERY_CACHE.get(query_key) if real_model else None
    if query_vectors is None:
        query_vectors = normalized_vectors(embedder.embed([QUERY_INSTRUCTION + part for part in parts]))
        if real_model:
            with _CACHE_LOCK:
                _QUERY_CACHE[query_key] = query_vectors
                while len(_QUERY_CACHE) > 64:
                    _QUERY_CACHE.popitem(last=False)
    embedded = time.perf_counter()
    scores = view['matrix'] @ query_vectors.T
    best = {}
    for path, positions in grouped.items():
        document_scores = scores[positions]
        strongest = document_scores.max(axis=0)
        score = strongest[0] if len(parts) == 1 else 0.55 * strongest[0] + 0.45 * strongest[1:].mean()
        representative = document_scores[:, 0] if len(parts) == 1 else 0.7 * document_scores[:, 0] + 0.3 * document_scores[:, 1:].mean(axis=1)
        position = positions[int(np.argmax(representative))]
        path, start, content, vector = view['chunks'][position]
        document = view['documents'][path]
        best[path] = {'file_name': document['file_name'], 'file_path': path, 'file_type': document['file_type'],
                      'snippet': content, 'match_start': start, 'score': float(score)}
    ordered = sorted(best.values(), key=lambda row: (-row['score'], row['file_path']))
    return {'total_count': len(best), 'results': ordered[:limit], 'description_parts': len(parts), 'stale': view['stale'],
            'timings': {'load_s': loaded-started, 'embed_s': embedded-loaded,
                        'rank_s': time.perf_counter()-embedded, 'total_s': time.perf_counter()-started}}


def warm_search(catalog_path, semantic_path):
    if Path(catalog_path).is_file() and _ready(semantic_path):
        view = snapshot(catalog_path, semantic_path)
        embedder = LocalEmbedder()
        digest = embedder.ensure_ready()
        if view['meta'].get('identity') != f'{MODEL}:{digest}:{RECIPE}':
            raise ValueError('Model değişmiş. Anlam dizinini yeniden hazırlayın.')
        embedder.embed(['Search Agent warmup'])

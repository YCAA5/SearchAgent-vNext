import json
import os
import sqlite3
import threading
import time
from contextlib import closing, contextmanager
from pathlib import Path

from catalog_state import metadata
from scope_paths import normalize_roots, path_key
from local_catalog import rebuild_catalog
from semantic_search import build_semantic_index, index_coverage, MODEL, RECIPE


def index_status(catalog, semantic, roots=None, ocr=None):
    state = {'can_search': False, 'current': False, 'reason': 'missing', 'chunks': 0}
    if not Path(catalog).is_file() or not Path(semantic).is_file():
        return state
    try:
        cat = metadata(catalog)
        with closing(sqlite3.connect(Path(semantic).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
            model = dict(connection.execute('SELECT key,value FROM metadata'))
            state['chunks'] = connection.execute('SELECT count(*) FROM chunks').fetchone()[0]
        # Readiness must not load the vector matrix or hash all document texts on the UI thread.
        with closing(sqlite3.connect(Path(catalog).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
            has_content = connection.execute("SELECT 1 FROM documents WHERE length(trim(content))>0 LIMIT 1").fetchone() is not None
        state['can_search'] = (has_content and state['chunks'] > 0 and model.get('ready') == '1' and
                               model.get('identity', '').startswith(MODEL + ':') and
                               model.get('identity', '').endswith(':' + RECIPE))
        state['current'] = state['can_search'] and cat.get('dirty') == '0' and cat.get('signature') == model.get('signature')
        state['reason'] = 'ready' if state['current'] else 'outdated'
        if roots is not None and sorted(path_key(p) for p in normalize_roots(roots)) != sorted(json.loads(cat.get('roots', '[]'))):
            state.update(current=False, reason='scope')
        if ocr is not None and cat.get('ocr') != str(bool(ocr)):
            state.update(current=False, reason='scope')
        if json.loads(cat.get('unavailable_roots', '[]')):
            state.update(current=False, reason='offline')
        return state
    except (OSError, ValueError, sqlite3.Error):
        return state


@contextmanager
def profile_lock(catalog):
    path = Path(catalog).parent / 'preparation.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0)
        if path.stat().st_size == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('Bu profil başka bir pencerede hazırlanıyor.') from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def prepare_all(roots, catalog, semantic, progress=None, cancel=None, ocr=False, embedder=None):
    cancel = cancel or threading.Event()
    started = time.perf_counter()
    def emit(stage, done, total, name):
        if progress:
            elapsed = time.perf_counter() - started
            eta = (total - done) * elapsed / done if total and done >= 5 and elapsed > 3 else None
            progress({'stage': stage, 'done': done, 'total': total, 'name': name, 'elapsed': elapsed, 'eta': eta})
    with profile_lock(catalog):
        scan = rebuild_catalog(roots, catalog, lambda count, path: emit('scan', count, None, path), cancel, ocr)
        emit('semantic', 0, scan['content'], '')
        vectors = build_semantic_index(catalog, semantic, lambda done, total, name: emit('semantic', done, total, name), cancel, embedder)
    return {'scan': scan, 'semantic': vectors, 'elapsed_s': time.perf_counter() - started}

import sqlite3
import threading
from contextlib import closing

import numpy as np
import pytest

from local_catalog import rebuild_catalog
from semantic_search import build_semantic_index, semantic_search, split_chunks


class FakeEmbedder:
    def __init__(self):
        self.calls = 0
        self.digest = 'test-model'

    def ensure_ready(self):
        return self.digest

    def embed(self, texts):
        self.calls += 1
        vectors = []
        for text in texts:
            vector = np.zeros(1024, dtype=np.float32)
            vector[0 if 'servis' in text or 'ulaşım' in text else 1] = 1
            vectors.append(vector)
        return vectors


def prepare(tmp_path):
    root = tmp_path / 'documents'
    root.mkdir()
    (root / 'budget.txt').write_text('Personel servis giderleri yıllık bütçe raporu.', encoding='utf-8')
    (root / 'food.txt').write_text('Yemekhane menüsü ve öğle yemeği tarifleri.', encoding='utf-8')
    catalog, semantic = tmp_path / 'catalog.db', tmp_path / 'semantic.db'
    rebuild_catalog([root], catalog)
    return root, catalog, semantic


def test_retrieval_preview_offset_filter_and_reuse(tmp_path):
    root, catalog, semantic = prepare(tmp_path)
    model = FakeEmbedder()
    report = build_semantic_index(catalog, semantic, embedder=model)
    assert report['documents'] == 2
    result = semantic_search(catalog, semantic, 'çalışanların ulaşım maliyeti', embedder=model)
    assert result['results'][0]['file_name'] == 'budget.txt'
    assert result['results'][0]['match_start'] == 0
    assert result['results'][0]['snippet'].startswith('Personel')
    assert semantic_search(catalog, semantic, 'ulaşım', extension='pdf', embedder=model)['total_count'] == 0
    calls = model.calls
    report = build_semantic_index(catalog, semantic, embedder=model)
    assert model.calls == calls
    assert report['cached'] == 2


def test_catalog_change_blocks_stale_results_then_removes_deleted_document(tmp_path):
    root, catalog, semantic = prepare(tmp_path)
    model = FakeEmbedder()
    build_semantic_index(catalog, semantic, embedder=model)
    (root / 'budget.txt').unlink()
    rebuild_catalog([root], catalog)
    with pytest.raises(ValueError, match='değişmiş'):
        semantic_search(catalog, semantic, 'ulaşım', embedder=model)
    report = build_semantic_index(catalog, semantic, embedder=model)
    assert report['cached'] == 1
    assert semantic_search(catalog, semantic, 'yemek', embedder=model)['total_count'] == 1
    with closing(sqlite3.connect(semantic)) as connection:
        assert connection.execute('SELECT count(*) FROM indexed_documents').fetchone()[0] == 1


def test_cancel_can_resume_without_reembedding_completed_documents(tmp_path):
    root, catalog, semantic = prepare(tmp_path)
    model = FakeEmbedder()
    cancel = threading.Event()
    def progress(done, total, name):
        if done >= 1:
            cancel.set()
    with pytest.raises(InterruptedError):
        build_semantic_index(catalog, semantic, progress, cancel, model)
    calls = model.calls
    report = build_semantic_index(catalog, semantic, embedder=model)
    assert report['cached'] == 2
    assert model.calls == calls


def test_changed_model_invalidates_vectors(tmp_path):
    root, catalog, semantic = prepare(tmp_path)
    model = FakeEmbedder()
    build_semantic_index(catalog, semantic, embedder=model)
    model.digest = 'new-version'
    with pytest.raises(ValueError, match='Model değişmiş'):
        semantic_search(catalog, semantic, 'ulaşım', embedder=model)
    assert build_semantic_index(catalog, semantic, embedder=model)['updated'] == 2


def test_chunk_coverage_and_offsets():
    text = ('uzun belge içeriği\n' * 500) + 'bitiş'
    chunks = list(split_chunks(text))
    assert chunks[0][0] == 0
    covered = 0
    for start, chunk in chunks:
        assert text[start:start + len(chunk)] == chunk
        assert start <= covered
        assert len(chunk) <= 2200
        covered = start + len(chunk)
    assert covered == len(text)


def test_invalid_embedding_rolls_back_document(tmp_path):
    root, catalog, semantic = prepare(tmp_path)
    class BrokenEmbedder(FakeEmbedder):
        def embed(self, texts):
            return [[float('nan')] * 1024 for text in texts]
    with pytest.raises(RuntimeError, match='geçersiz'):
        build_semantic_index(catalog, semantic, embedder=BrokenEmbedder())
    with closing(sqlite3.connect(semantic)) as connection:
        assert connection.execute('SELECT count(*) FROM indexed_documents').fetchone()[0] == 0


def test_summary_ranking_considers_all_remembered_details(tmp_path):
    root = tmp_path / 'documents'
    root.mkdir()
    (root / 'partial.txt').write_text('Only the first subject is discussed here.', encoding='utf-8')
    (root / 'complete.txt').write_text('Both subjects are discussed together here.', encoding='utf-8')
    catalog, semantic = tmp_path / 'catalog.db', tmp_path / 'semantic.db'
    rebuild_catalog([root], catalog)
    class DetailEmbedder(FakeEmbedder):
        def embed(self, texts):
            vectors = []
            for text in texts:
                vector = np.zeros(1024, dtype=np.float32)
                if text.startswith('Instruct:'):
                    values = [1, 0, 0] if 'birinci' in text and 'ikinci' in text else ([0, 1, 0] if 'birinci' in text else [0, 0, 1])
                else:
                    values = [0.8, 0.6, 0] if 'partial.txt' in text else [0.75, 0.5, 0.5]
                vector[:3] = values
                vectors.append(vector)
            return vectors
    model = DetailEmbedder()
    build_semantic_index(catalog, semantic, embedder=model)
    query = ('birinci konuda aklımda kalan önemli ayrıntılar ve yapılan değerlendirmeler ' * 2).strip() + '.\n'
    query += ('ikinci konudaki ayrı ayrıntıları ve bunların aynı belgede birlikte anlatıldığını hatırlıyorum ' * 2).strip() + '.'
    result = semantic_search(catalog, semantic, query, embedder=model)
    assert result['description_parts'] == 3
    assert result['results'][0]['file_name'] == 'complete.txt'


def test_long_description_parts_are_bounded():
    from semantic_search import description_parts
    parts = description_parts('Uzun bir hatırlama notu ve ilgili ayrıntılar ' * 130)
    assert 1 < len(parts) <= 5
    assert all(len(part) <= 2200 for part in parts)


def test_content_coverage_is_distinct_from_filename_count(tmp_path):
    from semantic_search import index_coverage
    root = tmp_path / 'documents'
    root.mkdir()
    (root / 'report.txt').write_text('Belgenin gerçek içeriği', encoding='utf-8')
    (root / 'model.blend').write_bytes(b'not-readable-as-text')
    catalog = tmp_path / 'catalog.db'
    rebuild_catalog([root], catalog)
    assert index_coverage(catalog) == {'files': 2, 'content': 1}

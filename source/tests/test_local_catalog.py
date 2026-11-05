import sqlite3
import threading

import pytest
import pymupdf

from local_catalog import rebuild_catalog, search_catalog


def test_content_filename_and_rebuild(tmp_path):
    source = tmp_path / 'documents'
    source.mkdir()
    (source / 'teklif.txt').write_text('Ankara savunma projesi', encoding='utf-8')
    drawing = source / 'Murat_ölçüm.blend'
    drawing.write_bytes(b'example')
    db_path = tmp_path / 'indexes' / 'catalog.db'
    report = rebuild_catalog([source, source], db_path)
    assert report['indexed'] == 2
    assert report['content'] == 1
    assert search_catalog(db_path, 'savunma')['total_count'] == 1
    assert search_catalog(db_path, 'ölçüm', 'Dosya adı')['total_count'] == 1
    assert search_catalog(db_path, 'ölçüm', 'Dosya adı', 'pdf')['total_count'] == 0
    drawing.unlink()
    rebuild_catalog([source], db_path)
    assert search_catalog(db_path, 'ölçüm', 'Dosya adı')['total_count'] == 0


def test_reader_failure_retains_filename_and_reports_error(tmp_path, monkeypatch):
    source = tmp_path / 'documents'
    source.mkdir()
    (source / 'broken.pdf').write_bytes(b'not pdf')
    def fail(path):
        raise ValueError('bozuk belge')
    monkeypatch.setattr('local_catalog.extract_content', fail)
    db_path = tmp_path / 'catalog.db'
    report = rebuild_catalog([source], db_path)
    assert report['name_only'] == 1
    assert 'bozuk belge' in report['errors'][0]
    assert search_catalog(db_path, 'broken', 'Dosya adı')['total_count'] == 1


def test_cancel_preserves_previous_index_and_cleans_temporary_file(tmp_path):
    source = tmp_path / 'documents'
    source.mkdir()
    (source / 'old.txt').write_text('önceki', encoding='utf-8')
    db_path = tmp_path / 'catalog.db'
    rebuild_catalog([source], db_path)
    before = db_path.read_bytes()
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(InterruptedError):
        rebuild_catalog([source], db_path, cancel=cancel)
    assert db_path.read_bytes() == before
    assert not list(tmp_path.glob('catalog-*.db'))


def test_skips_environment_and_index_and_overlapping_roots(tmp_path):
    source = tmp_path / 'documents'
    source.mkdir()
    nested = source / 'nested'
    nested.mkdir()
    (nested / 'visible.txt').write_text('visible', encoding='utf-8')
    excluded = source / '.venv'
    excluded.mkdir()
    (excluded / 'hidden.txt').write_text('hidden', encoding='utf-8')
    db_path = source / 'indexes' / 'catalog.db'
    report = rebuild_catalog([source, nested], db_path)
    assert report['indexed'] == 1
    with sqlite3.connect(db_path) as connection:
        assert connection.execute('SELECT file_name FROM documents').fetchall() == [('visible.txt',)]


def test_filename_search_escapes_wildcards(tmp_path):
    source = tmp_path / 'documents'
    source.mkdir()
    (source / 'plan_100%.txt').write_text('', encoding='utf-8')
    (source / 'planA100X.txt').write_text('', encoding='utf-8')
    db_path = tmp_path / 'catalog.db'
    rebuild_catalog([source], db_path)
    assert search_catalog(db_path, '_100%', 'Dosya adı')['total_count'] == 1


def test_pdf_text_and_scanned_pdf_without_ocr(tmp_path):
    source = tmp_path / 'documents'
    source.mkdir()
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), 'UniquePDFSearchTerm')
        document.save(source / 'text.pdf')
    with pymupdf.open() as document:
        document.new_page()
        document.save(source / 'scanned.pdf')
    db_path = tmp_path / 'catalog.db'
    report = rebuild_catalog([source], db_path)
    assert report['indexed'] == 2
    assert report['content'] == 1
    assert len(report['errors']) == 1
    assert search_catalog(db_path, 'UniquePDFSearchTerm')['total_count'] == 1
    assert search_catalog(db_path, 'scanned', 'Dosya adı')['total_count'] == 1

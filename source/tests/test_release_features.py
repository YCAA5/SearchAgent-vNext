import json
import zipfile
from pathlib import Path

import pytest

from i18n import translate
from ui_theme import extension_value, load_preferences, save_preferences
from tools.package_release import write_source_archive


def test_language_and_result_preferences_persist_without_losing_folders(tmp_path):
    path = tmp_path / 'preferences.json'
    path.write_text(json.dumps({'folders': ['D:\\Documents'], 'ocr_images': True, 'custom': 42}), encoding='utf-8')
    save_preferences(path, {'language': 'en', 'result_size': 'large', 'result_view': 'list'})
    loaded = load_preferences(path, [])
    assert loaded['folders'] == ['D:\\Documents']
    assert loaded['ocr_images'] is True
    assert loaded['custom'] == 42
    assert (loaded['language'], loaded['result_size'], loaded['result_view']) == ('en', 'large', 'list')


def test_unknown_preferences_fall_back_safely(tmp_path):
    path = tmp_path / 'preferences.json'
    path.write_text(json.dumps({'folders': [], 'language': 'other', 'result_size': 'huge', 'result_view': 'tiles'}), encoding='utf-8')
    loaded = load_preferences(path, [])
    assert (loaded['language'], loaded['result_size'], loaded['result_view']) == ('tr', 'medium', 'cards')


def test_english_ui_text_and_filter_are_not_applied_to_documents():
    assert translate('Klasörler', 'en') == 'Folders'
    assert translate('Çalışma alanı  /  Arama', 'en') == 'Workspace  /  Search'
    assert translate('17 aday', 'en') == '17 candidates'
    assert translate('Sayfa 2 / 9', 'en') == 'Page 2 / 9'
    assert extension_value('All files') == ''
    assert translate('An unknown document title', 'en') == 'An unknown document title'


def test_source_export_does_not_include_personal_data_or_binaries(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    files = ['main.py', 'README.md', 'requirements.txt', 'config/example.json', 'config/desktop.json',
             '.env', 'data/indexes/desktop.db', 'logs/private.log', '.runtime/models/weights.bin',
             '.venv/secret.py', 'dist/SearchAgent/SearchAgent.exe', 'tests/test_sample.py']
    for name in files:
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('private' if name in {'config/desktop.json', '.env'} else 'sample', encoding='utf-8')
    archive = write_source_archive(project, tmp_path / 'source.zip')
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        assert 'SearchAgent/main.py' in names
        assert 'SearchAgent/config/example.json' in names
        assert 'SearchAgent/tests/test_sample.py' in names
        assert not any('desktop.json' in name or name.endswith('.env') or '.runtime/' in name or '.venv/' in name or '/data/' in name or '/logs/' in name or '/dist/' in name for name in names)


def test_frozen_profile_is_separate_from_application_folder(tmp_path, monkeypatch):
    import app_paths
    monkeypatch.delenv('SEARCH_AGENT_HOME', raising=False)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    monkeypatch.setattr(app_paths, 'FROZEN', True)
    assert app_paths.data_directory() == tmp_path / 'local' / 'SearchAgent-vNext'


@pytest.mark.skipif(__import__('os').name != 'nt', reason='Windows native runtime compatibility')
def test_bundled_ocr_works_from_unicode_installation_directory(tmp_path, monkeypatch):
    import app_paths
    source = tmp_path / 'Türkçe ı ş' / 'tesseract'
    (source / 'tessdata').mkdir(parents=True)
    (source / 'tesseract.exe').write_bytes(b'executable')
    (source / 'tessdata' / 'tur.traineddata').write_bytes(b'language-v1')
    monkeypatch.setattr(app_paths, 'DATA_ROOT', tmp_path / 'profile')
    target = app_paths.ocr_runtime_directory(source)
    assert str(target).isascii()
    assert (target / 'tesseract.exe').read_bytes() == b'executable'
    assert (target / 'tessdata' / 'tur.traineddata').read_bytes() == b'language-v1'
    (source / 'tessdata' / 'tur.traineddata').write_bytes(b'language-version-two')
    assert (app_paths.ocr_runtime_directory(source) / 'tessdata' / 'tur.traineddata').read_bytes() == b'language-version-two'

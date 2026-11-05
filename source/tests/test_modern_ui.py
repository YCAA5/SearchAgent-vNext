import customtkinter as ctk
import pytest
from PIL import Image

import desktop_app
from desktop_app import SearchApp
from ui_theme import load_preferences


@pytest.fixture
def app(tmp_path, monkeypatch, tk_root):
    monkeypatch.setattr(desktop_app, 'SETTINGS', tmp_path / 'preferences.json')
    monkeypatch.setattr(desktop_app, 'DATABASE', tmp_path / 'catalog.db')
    monkeypatch.setattr(desktop_app, 'SEMANTIC_DATABASE', tmp_path / 'semantic.db')
    window = ctk.CTkToplevel(tk_root)
    window.withdraw()
    application = SearchApp(window)
    window.update_idletasks()
    yield application
    application.close()


def test_switch_theme_keeps_query_results_selection_and_folders(app):
    app.query.insert('1.0', 'Dosyadan hatırladığım uzun açıklama')
    rows = [{'file_name': 'example.txt', 'file_path': 'D:\\Docs\\example.txt', 'file_type': '.txt', 'snippet': 'ilgili paragraf', 'score': 0.6}]
    app.preview = lambda event=None: None
    app.display_results({'results': rows, 'total_count': 1, 'semantic': True})
    app.display_preview({'document': {'file_name': 'example.txt', 'file_path': 'D:\\Docs\\example.txt', 'file_size': 123,
                                     'modified_at': '2026-11-04T12:00:00', 'content': 'ilgili paragraf'},
                         'text': 'ilgili paragraf', 'match': 'ilgili paragraf', 'image': Image.new('RGB', (160, 200), 'white'),
                         'page': 1, 'pages': 2, 'notice': ''})
    app.show_preview_mode('image')
    photo = app.photo
    folders = app.folders.get(0, 'end')
    app.change_theme('Koyu')
    assert app.theme == 'dark'
    assert app.query.get('1.0', 'end-1c') == 'Dosyadan hatırladığım uzun açıklama'
    assert app.selected_id == '0'
    assert app.rows['0'] == rows[0]
    assert app.photo is photo
    assert app.preview_mode == 'image'
    assert 'ilgili paragraf' in app.preview_text.get('1.0', 'end-1c')
    assert app.folders.get(0, 'end') == folders
    assert load_preferences(desktop_app.SETTINGS, [])['theme'] == 'dark'
    app.change_theme('Açık')
    assert load_preferences(desktop_app.SETTINGS, [])['theme'] == 'light'


def test_sidebar_and_preview_modes_are_functional(app):
    for title in ('Klasörler', 'Dizin durumu', 'Ayarlar', 'Arama'):
        app.show_page(title)
        assert app.active_page == title
    app.show_preview_mode('image')
    assert app.preview_mode == 'image'
    app.show_preview_mode('text')
    assert app.preview_mode == 'text'


def test_all_files_filter_never_becomes_literal_extension(app, monkeypatch):
    calls = []
    monkeypatch.setattr(desktop_app, 'semantic_search', lambda catalog, index, query, extension, **kwargs: calls.append(extension) or {'results': [], 'total_count': 0})
    app.start_task = lambda kind, function, message: function()
    app.ready_status = {'can_search': True, 'current': True}
    app.query.insert('1.0', 'Aklımdaki açıklama')
    app.search()
    assert calls == ['']
    app.extension.set('PDF')
    app.search()
    assert calls == ['', 'pdf']
    assert app.extension.cget('state') == 'normal'
    app.extension.set('.jsonl')
    app.search()
    assert calls[-1] == 'jsonl'

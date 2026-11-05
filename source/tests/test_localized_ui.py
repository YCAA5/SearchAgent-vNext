import customtkinter as ctk
import pytest
from PIL import Image

import desktop_app


def test_language_size_and_view_switches_preserve_query_and_preview(tk_root, tmp_path, monkeypatch):
    monkeypatch.setattr(desktop_app, 'SETTINGS', tmp_path / 'settings.json')
    monkeypatch.setattr(desktop_app, 'DATABASE', tmp_path / 'catalog.db')
    monkeypatch.setattr(desktop_app, 'SEMANTIC_DATABASE', tmp_path / 'semantic.db')
    window = ctk.CTkToplevel(tk_root)
    window.withdraw()
    app = desktop_app.SearchApp(window)
    try:
        app.query.insert('1.0', 'Türkçe hatırlama notu and English description')
        app.preview = lambda event=None: None
        app.display_results({'results': [{'file_name': 'Arama', 'file_path': 'D:\\Documents\\Arama', 'file_type': '.txt', 'snippet': 'Dosyanın orijinal Türkçe metni', 'score': 0.5}], 'total_count': 1})
        app.display_preview({'document': {'file_name': 'Arama', 'file_path': 'D:\\Documents\\Arama', 'file_size': 100, 'modified_at': '', 'content': 'Dosyanın orijinal Türkçe metni'},
                             'text': 'Dosyanın orijinal Türkçe metni', 'image': Image.new('RGB', (100, 100), 'white'), 'page': 1, 'pages': 2, 'notice': ''})
        app.show_preview_mode('image')
        photo = app.photo
        app.change_language('English')
        assert app.nav_buttons['Klasörler'].cget('text') == 'Folders'
        assert app.preview_title.get() == 'Arama'
        assert app.cards['0'][1].cget('text') == 'Arama'
        assert app.query.get('1.0', 'end-1c') == 'Türkçe hatırlama notu and English description'
        assert 'orijinal Türkçe' in app.preview_text.get('1.0', 'end-1c')
        for label, expected in [('Small', 28), ('Medium', 42), ('Large', 64)]:
            app.change_result_size(label)
            assert app.badges['0'].cget('width') == expected
            assert app.selected_id == '0'
            assert app.photo is photo
        app.change_result_view('List')
        assert not app.cards['0'][2].winfo_manager()
        app.change_result_view('Cards')
        assert app.cards['0'][2].winfo_manager() == 'grid'
        app.change_language('Türkçe')
        assert app.nav_buttons['Klasörler'].cget('text') == 'Klasörler'
    finally:
        app.close()

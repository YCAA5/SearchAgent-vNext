import json

import pytest

from ui_theme import DARK, LIGHT, extension_value, load_preferences, save_preferences


def test_theme_preference_preserves_folders_ocr_and_unknown_settings(tmp_path):
    path = tmp_path / 'preferences.json'
    path.write_text(json.dumps({'folders': ['D:\\Belgeler'], 'ocr_images': True, 'custom_flag': 12}), encoding='utf-8')
    save_preferences(path, {'theme': 'dark'})
    loaded = load_preferences(path, [])
    assert loaded['theme'] == 'dark'
    assert loaded['folders'] == ['D:\\Belgeler']
    assert loaded['ocr_images'] is True
    assert loaded['custom_flag'] == 12


def test_failed_atomic_save_preserves_original_settings(tmp_path, monkeypatch):
    path = tmp_path / 'preferences.json'
    original = '{"folders": ["D:\\\\Belgeler"], "theme": "light"}'
    path.write_text(original, encoding='utf-8')
    def fail(source, destination):
        raise PermissionError('test write failure')
    monkeypatch.setattr('ui_theme.os.replace', fail)
    with pytest.raises(PermissionError):
        save_preferences(path, {'theme': 'dark'})
    assert path.read_text(encoding='utf-8') == original
    assert not list(tmp_path.glob('preferences-*.tmp'))


def test_invalid_settings_are_not_silently_overwritten(tmp_path):
    path = tmp_path / 'preferences.json'
    path.write_text('not json', encoding='utf-8')
    with pytest.raises(ValueError):
        save_preferences(path, {'theme': 'dark'})
    assert path.read_text(encoding='utf-8') == 'not json'


def test_defaults_and_filter_labels(tmp_path):
    assert load_preferences(tmp_path / 'missing.json', ['D:\\Docs'])['theme'] == 'light'
    assert extension_value('Tüm dosyalar') == ''
    assert extension_value(' XLSX ') == 'xlsx'
    assert extension_value('.pdf') == 'pdf'


def test_theme_text_contrast():
    def luminance(hex_color):
        channels = [int(hex_color[position:position + 2], 16) / 255 for position in (1, 3, 5)]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
        return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    for palette in (LIGHT, DARK):
        for foreground, background in [('text', 'surface'), ('muted', 'surface'), ('accent_text', 'accent')]:
            values = sorted([luminance(palette[foreground]), luminance(palette[background])])
            assert (values[1] + 0.05) / (values[0] + 0.05) >= 4.5

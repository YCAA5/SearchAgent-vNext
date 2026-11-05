import json
import os
import tempfile
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw
from app_paths import resource_path


LIGHT = {
    'background': '#F5F6F3', 'sidebar': '#EBEEEA', 'surface': '#FFFFFF',
    'text': '#172029', 'muted': '#64716D', 'border': '#DCE2DD',
    'accent': '#007F68', 'accent_hover': '#006753', 'accent_text': '#FFFFFF',
    'soft': '#E1F2EC', 'hover': '#EDF3EF', 'highlight': '#FFF0B3',
    'highlight_text': '#262B22', 'success': '#287853', 'danger': '#BA3939',
}
DARK = {
    'background': '#171B23', 'sidebar': '#11151C', 'surface': '#222833',
    'text': '#F1F3F5', 'muted': '#A7B1BC', 'border': '#37404D',
    'accent': '#F2B352', 'accent_hover': '#E6A23D', 'accent_text': '#191C22',
    'soft': '#3C3328', 'hover': '#2D3440', 'highlight': '#285A50',
    'highlight_text': '#F1FFF9', 'success': '#80C5AA', 'danger': '#F08C8C',
}


def color(token):
    return LIGHT[token], DARK[token]


def number(value):
    return f'{value:,}'.replace(',', '.')


def load_preferences(path, default_folders):
    path = Path(path)
    settings = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    if not isinstance(settings, dict):
        raise ValueError('Ayar dosyasının biçimi geçersiz.')
    folders = settings.get('folders', default_folders)
    if not isinstance(folders, list) or not all(isinstance(folder, str) and folder.strip() for folder in folders):
        raise ValueError('Klasör ayarları geçersiz.')
    return {**settings, 'folders': folders,
            'theme': settings.get('theme') if settings.get('theme') in {'light', 'dark'} else 'light',
            'language': settings.get('language') if settings.get('language') in {'tr', 'en'} else 'tr',
            'result_size': settings.get('result_size') if settings.get('result_size') in {'small', 'medium', 'large'} else 'medium',
            'result_view': settings.get('result_view') if settings.get('result_view') in {'cards', 'list'} else 'cards',
            'ocr_images': settings.get('ocr_images') is True}


def save_preferences(path, values):
    path = Path(path)
    settings = load_preferences(path, [])
    settings.update(values)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='preferences-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(settings, output, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def extension_value(value):
    return '' if value in {'Tüm dosyalar', 'All files'} else value.strip().lower().lstrip('.')


def icon(name, size=22, primary=False):
    asset = resource_path('assets/app-icon.png')
    if name == 'brand' and asset.is_file():
        with Image.open(asset) as image:
            picture = image.copy()
        return ctk.CTkImage(light_image=picture, dark_image=picture, size=(size, size))
    def draw_icon(stroke):
        image = Image.new('RGBA', (96, 96), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        if name in {'search', 'brand'}:
            if name == 'brand':
                draw.line([(12, 75), (12, 25), (37, 25), (45, 36), (83, 36), (83, 75)], fill=stroke, width=7)
            draw.ellipse((27, 35, 61, 69), outline=stroke, width=7)
            draw.line((58, 65, 79, 85), fill=stroke, width=7)
        elif name == 'folder':
            draw.line([(12, 75), (12, 25), (37, 25), (46, 36), (83, 36), (83, 75), (12, 75)], fill=stroke, width=6)
        elif name == 'layers':
            for offset in (0, 18, 36):
                draw.line([(13, 27 + offset), (48, 11 + offset), (83, 27 + offset), (48, 44 + offset), (13, 27 + offset)], fill=stroke, width=5)
        elif name == 'settings':
            draw.ellipse((29, 29, 67, 67), outline=stroke, width=6)
            for start, end in [((48, 10), (48, 27)), ((48, 69), (48, 86)), ((10, 48), (27, 48)), ((69, 48), (86, 48)), ((21, 21), (33, 33)), ((63, 63), (75, 75)), ((21, 75), (33, 63)), ((63, 33), (75, 21))]:
                draw.line([start, end], fill=stroke, width=8)
        elif name == 'check':
            draw.ellipse((13, 13, 83, 83), outline=stroke, width=6)
            draw.line([(29, 48), (42, 61), (68, 34)], fill=stroke, width=7)
        else:
            draw.rounded_rectangle((13, 18, 83, 69), radius=6, outline=stroke, width=6)
            draw.line([(48, 70), (48, 84), (29, 84), (67, 84)], fill=stroke, width=6)
        return image
    token = 'accent' if primary else 'text'
    return ctk.CTkImage(light_image=draw_icon(LIGHT[token]), dark_image=draw_icon(DARK[token]), size=(size, size))

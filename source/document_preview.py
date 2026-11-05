import sqlite3
from contextlib import closing
from pathlib import Path

import pymupdf
from PIL import Image
from format_readers import IMAGE_EXTENSIONS


def document_preview(catalog_path, file_path, match_start=None, snippet='', width=600, height=600):
    with closing(sqlite3.connect(Path(catalog_path).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute('SELECT * FROM documents WHERE file_path=?', (str(file_path),)).fetchone()
        if row is None:
            raise ValueError('Dosya dizinde bulunamadı. Aramayı yenileyin.')
        document = dict(row)
    content = document['content'] or ''
    clean_snippet = snippet.replace('<mark>', '').replace('</mark>', '').strip(' .\n')
    if match_start is None:
        match_start = content.find(clean_snippet) if clean_snippet else 0
    match_start = max(0, min(match_start, len(content)))
    start = max(0, match_start - 350)
    text = content[start:start + 16000]
    if start:
        text = '…\n' + text
    if start + 16000 < len(content):
        text += '\n… (önizleme kısaltıldı)'
    result = {'document': document, 'text': text or 'Bu dosyanın metin içeriği dizinde yok. Dosya adıyla aranabilir.',
              'image': None, 'page': None, 'pages': None, 'notice': ''}
    path = Path(file_path)
    if not path.is_file():
        result['notice'] = 'Dosya taşınmış veya silinmiş; son dizinlenen metin gösteriliyor.'
        return result
    try:
        stat = path.stat()
        if stat.st_size != document['file_size']:
            result['notice'] = 'Dosya değişmiş olabilir. Metin son dizinlemeden; görsel güncel dosyadandır.'
        if path.suffix.lower() == '.pdf':
            with pymupdf.open(path) as pdf:
                page_number = 0
                target = clean_snippet[:100] or content[match_start:match_start + 100]
                if target:
                    needle = ' '.join(target.split()).casefold()
                    for page_number, page in enumerate(pdf):
                        if needle in ' '.join(page.get_text('text').split()).casefold():
                            break
                    else:
                        page_number = 0
                page = pdf[page_number]
                scale = min(width / page.rect.width, height / page.rect.height, 1.5)
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                result['image'] = pixmap.pil_image().copy()
                result['page'] = page_number + 1
                result['pages'] = len(pdf)
        elif path.suffix.lower() in IMAGE_EXTENSIONS:
            with Image.open(path) as image:
                image.thumbnail((width, height))
                result['image'] = image.convert('RGB').copy()
    except Exception as error:
        result['notice'] = f'Görsel önizleme açılamadı: {error}'
    return result

import pymupdf
from PIL import Image

from document_preview import document_preview
from local_catalog import rebuild_catalog


def test_pdf_preview_locates_matching_page(tmp_path):
    root = tmp_path / 'documents'
    root.mkdir()
    path = root / 'example.pdf'
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), 'First page heading')
        document.new_page().insert_text((72, 72), 'Unique second page matching text')
        document.save(path)
    catalog = tmp_path / 'catalog.db'
    rebuild_catalog([root], catalog)
    preview = document_preview(catalog, str(path), snippet='Unique second page matching text')
    assert preview['page'] == 2
    assert preview['pages'] == 2
    assert preview['image'].width <= 600
    assert 'Unique second page' in preview['text']


def test_missing_file_still_previews_indexed_text(tmp_path):
    root = tmp_path / 'documents'
    root.mkdir()
    path = root / 'text.txt'
    path.write_text('Son dizinlenen belge içeriği.', encoding='utf-8')
    catalog = tmp_path / 'catalog.db'
    rebuild_catalog([root], catalog)
    path.unlink()
    preview = document_preview(catalog, str(path))
    assert 'Son dizinlenen' in preview['text']
    assert 'silinmiş' in preview['notice']


def test_match_late_in_long_file_is_visible(tmp_path):
    root = tmp_path / 'documents'
    root.mkdir()
    path = root / 'long.txt'
    text = 'ilk bölüm ' * 4000 + 'Hedef metin burada'
    path.write_text(text, encoding='utf-8')
    catalog = tmp_path / 'catalog.db'
    rebuild_catalog([root], catalog)
    preview = document_preview(catalog, str(path), match_start=text.index('Hedef'))
    assert 'Hedef metin burada' in preview['text']
    assert len(preview['text']) < 17000


def test_image_preview_is_bounded_and_keeps_source_unchanged(tmp_path):
    root = tmp_path / 'documents'
    root.mkdir()
    path = root / 'image.png'
    with Image.new('RGB', (1600, 1000), 'navy') as image:
        image.save(path)
    original = path.read_bytes()
    catalog = tmp_path / 'catalog.db'
    rebuild_catalog([root], catalog)
    preview = document_preview(catalog, str(path), width=400, height=300)
    assert preview['image'].size == (400, 250)
    assert path.read_bytes() == original

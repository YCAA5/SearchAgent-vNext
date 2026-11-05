import codecs
import posixpath
import re
import shutil
import zipfile
from email import policy
from email.parser import BytesParser
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
from defusedxml import ElementTree
from PIL import Image
from app_paths import find_tesseract


TEXT_EXTENSIONS = {
    '.md', '.markdown', '.rst', '.log', '.json', '.jsonl', '.yaml', '.yml',
    '.toml', '.ini', '.cfg', '.conf', '.tsv', '.sql', '.py', '.js', '.ts',
    '.tsx', '.jsx', '.cs', '.c', '.cpp', '.h', '.hpp', '.css', '.scss',
    '.ps1', '.sh', '.bat', '.cmd', '.tex', '.srt', '.vtt',
}
XML_EXTENSIONS = {'.xml', '.svg'}
SPREADSHEET_EXTENSIONS = {'.xls', '.xlsb', '.xlsm', '.ods'}
PACKAGE_EXTENSIONS = {'.odt', '.odp', '.docm', '.pptm', '.epub'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.jpe', '.webp', '.bmp', '.gif', '.tif', '.tiff', '.tga', '.psd'}
EXTRA_EXTENSIONS = TEXT_EXTENSIONS | XML_EXTENSIONS | SPREADSHEET_EXTENSIONS | PACKAGE_EXTENSIONS | {'.rtf', '.eml'}
MAX_EXPANDED_BYTES = 64 * 1024 * 1024


def decode_text(data):
    if data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        text = data.decode('utf-32')
    elif data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        text = data.decode('utf-16')
    else:
        if b'\x00' in data:
            raise ValueError('Metin dosyasında ikili veri bulundu.')
        for encoding in ('utf-8-sig', 'cp1254', 'latin-1'):
            try:
                text = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
    controls = sum(ord(character) < 32 and character not in '\r\n\t' for character in text)
    if controls > max(2, len(text) // 100):
        raise ValueError('Dosya okunabilir metin içermiyor.')
    return text


def html_text(text):
    soup = BeautifulSoup(text, 'html.parser')
    for element in soup(['script', 'style', 'noscript']):
        element.decompose()
    return soup.get_text(' ', strip=True)


def xml_text(data, paragraphs_only=False, svg=False):
    root = ElementTree.fromstring(data)
    if svg:
        return '\n'.join(' '.join(element.itertext()).strip() for element in root.iter()
                         if element.tag.rsplit('}', 1)[-1] in {'text', 'title', 'desc'})
    if paragraphs_only:
        return '\n'.join(' '.join(element.itertext()).strip() for element in root.iter()
                         if element.tag.rsplit('}', 1)[-1] in {'p', 'h'})
    return '\n'.join(text.strip() for text in root.itertext() if text.strip())


def checked_archive(path):
    archive = zipfile.ZipFile(path)
    if sum(info.file_size for info in archive.infolist()) > MAX_EXPANDED_BYTES:
        archive.close()
        raise ValueError('Belgenin açılmış içeriği 64 MB sınırını aşıyor.')
    return archive


def read_epub(archive):
    container = ElementTree.fromstring(archive.read('META-INF/container.xml'))
    package_path = next(element.attrib['full-path'] for element in container.iter()
                        if element.tag.rsplit('}', 1)[-1] == 'rootfile')
    package = ElementTree.fromstring(archive.read(package_path))
    manifest = {element.attrib['id']: element.attrib for element in package.iter()
                if element.tag.rsplit('}', 1)[-1] == 'item'}
    sections = []
    for element in package.iter():
        if element.tag.rsplit('}', 1)[-1] != 'itemref':
            continue
        item = manifest.get(element.attrib.get('idref'), {})
        if item.get('media-type') not in {'application/xhtml+xml', 'text/html'}:
            continue
        href = urlsplit(item['href'])
        if href.scheme or href.netloc:
            continue
        member = posixpath.normpath(posixpath.join(posixpath.dirname(package_path), unquote(href.path)))
        if member.startswith('../') or member.startswith('/'):
            raise ValueError('EPUB içindeki bölüm yolu geçersiz.')
        sections.append(html_text(archive.read(member)))
    return '\n'.join(sections)


def read_package(path):
    with checked_archive(path) as archive:
        if path.suffix.lower() == '.epub':
            return read_epub(archive)
        if path.suffix.lower() in {'.odt', '.odp'}:
            return xml_text(archive.read('content.xml'), paragraphs_only=True)
        if path.suffix.lower() == '.docm':
            members = [name for name in archive.namelist() if name == 'word/document.xml'
                       or name.startswith(('word/header', 'word/footer')) and name.endswith('.xml')]
        else:
            members = sorted([name for name in archive.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', name)],
                             key=lambda name: int(Path(name).stem[5:]))
        return '\n'.join(xml_text(archive.read(name)) for name in members)


def read_spreadsheet(path):
    from python_calamine import CalamineWorkbook
    if zipfile.is_zipfile(path):
        with checked_archive(path):
            pass
    parts = []
    with CalamineWorkbook.from_path(path) as workbook:
        for name in workbook.sheet_names:
            parts.append(name)
            for row in workbook.get_sheet_by_name(name).iter_rows():
                values = [str(value) for value in row if value is not None and value != '']
                if values:
                    parts.append(' | '.join(values))
    return '\n'.join(parts)


def read_email(path):
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    headers = [f'{name}: {message[name]}' for name in ('Subject', 'From', 'To', 'Date') if message[name]]
    body = message.get_body(preferencelist=('plain', 'html'))
    content = '' if body is None else body.get_content()
    if body is not None and body.get_content_type() == 'text/html':
        content = html_text(content)
    return '\n'.join(headers + [content])


@lru_cache(maxsize=1)
def ocr_configuration():
    import os
    import pytesseract
    executable = find_tesseract()
    if not executable:
        raise RuntimeError('Resim yazılarını okumak için Tesseract kurulu olmalı.')
    pytesseract.pytesseract.tesseract_cmd = executable
    languages = pytesseract.get_languages(config='')
    selected = [language for language in ('tur', 'eng') if language in languages]
    if not selected:
        raise RuntimeError('Tesseract Türkçe veya İngilizce dil verisi bulunamadı.')
    return '+'.join(selected)


def read_image_text(path):
    import pytesseract
    languages = ocr_configuration()
    with Image.open(path) as source:
        source.seek(0)
        source.thumbnail((2800, 2800))
        with source.convert('RGB') as image:
            return pytesseract.image_to_string(image, lang=languages, timeout=25).strip()


def read_extended(path):
    path = Path(path)
    extension = path.suffix.lower()
    if extension in TEXT_EXTENSIONS:
        return decode_text(path.read_bytes())
    if extension in XML_EXTENSIONS:
        return xml_text(path.read_bytes(), svg=extension == '.svg')
    if extension in SPREADSHEET_EXTENSIONS:
        return read_spreadsheet(path)
    if extension in PACKAGE_EXTENSIONS:
        return read_package(path)
    if extension == '.rtf':
        from striprtf.striprtf import rtf_to_text
        data = path.read_bytes()
        codepage = re.search(rb'\\ansicpg(\d+)', data)
        encoding = 'cp' + codepage[1].decode('ascii') if codepage else 'cp1254'
        return rtf_to_text(data.decode(encoding), encoding='cp1254')
    if extension == '.eml':
        return read_email(path)
    raise ValueError(f'Desteklenmeyen belge türü: {extension}')

import zipfile
from email.message import EmailMessage

import pytest
from openpyxl import Workbook
from PIL import Image
from defusedxml.common import DefusedXmlException

from format_readers import decode_text, read_extended
from local_catalog import rebuild_catalog, search_catalog


@pytest.mark.parametrize('extension', ['.md', '.json', '.yaml', '.log', '.py', '.cs', '.tsv'])
def test_text_formats_are_indexed_without_executing_code(tmp_path, extension):
    root = tmp_path / 'documents'
    root.mkdir()
    path = root / ('sample' + extension)
    path.write_text('Türkçe bütçe açıklaması; personel servis giderleri', encoding='utf-8')
    catalog = tmp_path / 'catalog.db'
    report = rebuild_catalog([root], catalog)
    assert report['content'] == 1
    assert search_catalog(catalog, 'personel')['total_count'] == 1
    assert report['formats'][extension] == 1


@pytest.mark.parametrize('encoding', ['utf-8-sig', 'utf-16', 'utf-32', 'cp1254'])
def test_turkish_encodings(encoding):
    assert decode_text('İş güvenliği ölçümleri'.encode(encoding)) == 'İş güvenliği ölçümleri'


def test_binary_disguised_as_text_is_rejected():
    with pytest.raises(ValueError, match='ikili'):
        decode_text(b'header\x00binary')


def test_xml_extracts_text_but_rejects_entities(tmp_path):
    path = tmp_path / 'report.xml'
    path.write_text('<report><title>Servis giderleri</title><sum>100</sum></report>', encoding='utf-8')
    assert 'Servis giderleri' in read_extended(path)
    path.write_text('<!DOCTYPE root [<!ENTITY secret SYSTEM "file:///does-not-exist">]><root>&secret;</root>', encoding='utf-8')
    with pytest.raises(DefusedXmlException):
        read_extended(path)


def test_svg_reads_labels_not_geometry(tmp_path):
    path = tmp_path / 'diagram.svg'
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><title>Motor planı</title><text>Soğutma sistemi</text><path d="M 0 0 L 10 10"/></svg>', encoding='utf-8')
    text = read_extended(path)
    assert 'Soğutma sistemi' in text
    assert 'M 0 0' not in text


def test_email_uses_body_and_headers_without_attachments(tmp_path):
    message = EmailMessage()
    message['Subject'] = 'Teklif değerlendirmesi'
    message['From'] = 'example@example.com'
    message.set_content('Servis hizmetinin aylık bedeli belirlendi.')
    message.add_attachment(b'gizli-ek-icerigi', maintype='application', subtype='octet-stream', filename='attachment.bin')
    path = tmp_path / 'message.eml'
    path.write_bytes(message.as_bytes())
    text = read_extended(path)
    assert 'Teklif değerlendirmesi' in text
    assert 'aylık bedeli' in text
    assert 'gizli-ek-icerigi' not in text


def test_email_does_not_read_an_attached_message(tmp_path):
    message = EmailMessage()
    message.set_content('Main message body')
    attachment = EmailMessage()
    attachment.set_content('Attached message secret body')
    message.add_attachment(attachment)
    path = tmp_path / 'attached.eml'
    path.write_bytes(message.as_bytes())
    text = read_extended(path)
    assert 'Main message body' in text
    assert 'Attached message secret body' not in text


def test_email_html_body_without_plain_part(tmp_path):
    message = EmailMessage()
    message.set_content('<p>Teklif açıklaması</p><script>hidden script</script>', subtype='html')
    path = tmp_path / 'html.eml'
    path.write_bytes(message.as_bytes())
    text = read_extended(path)
    assert 'Teklif açıklaması' in text
    assert 'hidden script' not in text


@pytest.mark.parametrize('extension', ['.odt', '.odp'])
def test_open_document_packages(tmp_path, extension):
    path = tmp_path / ('report' + extension)
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('content.xml', '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><text:p>Personel ulaşım bütçesi</text:p></office:body></office:document-content>')
    assert 'Personel ulaşım bütçesi' in read_extended(path)


def test_epub_follows_reading_order_and_ignores_scripts(tmp_path):
    path = tmp_path / 'book.epub'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="OEBPS/package.opf"/></rootfiles></container>')
        archive.writestr('OEBPS/package.opf', '<package><manifest><item id="first" href="first.xhtml" media-type="application/xhtml+xml"/><item id="second" href="second.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="second"/><itemref idref="first"/></spine></package>')
        archive.writestr('OEBPS/first.xhtml', '<p>First chapter</p><script>not searchable script</script>')
        archive.writestr('OEBPS/second.xhtml', '<p>Second chapter</p>')
    text = read_extended(path)
    assert text.index('Second') < text.index('First')
    assert 'not searchable script' not in text


def test_rtf_unicode_and_escaped_text(tmp_path):
    path = tmp_path / 'report.rtf'
    path.write_bytes(br'{\rtf1\ansi\ansicpg1254 Personel servis giderleri \u351?irket}')
    text = read_extended(path)
    assert 'servis giderleri' in text
    assert 'şirket' in text


def test_macro_excel_reads_cells_and_closes_source(tmp_path):
    path = tmp_path / 'report.xlsm'
    workbook = Workbook()
    workbook.active['A1'] = 'Personel bütçesi'
    workbook.active['B1'] = 1234
    workbook.save(path)
    workbook.close()
    text = read_extended(path)
    assert 'Personel bütçesi' in text
    assert '1234' in text
    path.rename(tmp_path / 'closed.xlsm')


def test_unchanged_text_is_reused_and_ocr_is_opt_in(tmp_path, monkeypatch):
    root = tmp_path / 'documents'
    root.mkdir()
    (root / 'readme.md').write_text('Personel bütçesi', encoding='utf-8')
    with Image.new('RGB', (50, 50), 'white') as image:
        image.save(root / 'photo.png')
    catalog = tmp_path / 'catalog.db'
    assert rebuild_catalog([root], catalog)['content'] == 1
    monkeypatch.setattr('local_catalog.read_image_text', lambda path: 'Fotoğraf üzerindeki duyuru yazısı')
    report = rebuild_catalog([root], catalog, ocr=True)
    assert report['reused'] == 1
    assert report['content'] == 2
    assert search_catalog(catalog, 'duyuru')['total_count'] == 1
    assert rebuild_catalog([root], catalog, ocr=False)['content'] == 1


def test_generated_unity_code_is_name_only_but_user_code_is_searchable(tmp_path):
    root = tmp_path / 'UnityProject'
    (root / 'Assets').mkdir(parents=True)
    (root / 'ProjectSettings').mkdir()
    (root / 'Library').mkdir()
    (root / 'Library' / 'generated.cs').write_text('generatedCacheContent', encoding='utf-8')
    (root / 'Assets' / 'player.cs').write_text('Player movement and inventory', encoding='utf-8')
    catalog = tmp_path / 'catalog.db'
    report = rebuild_catalog([root], catalog)
    assert report['indexed'] == 2
    assert report['content'] == 1
    assert report['generated_name_only'] == 1
    assert rebuild_catalog([root / 'Library'], tmp_path / 'explicit.db')['content'] == 1


def test_ods_spreadsheet_cells(tmp_path):
    path = tmp_path / 'budget.ods'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('mimetype', 'application/vnd.oasis.opendocument.spreadsheet')
        archive.writestr('META-INF/manifest.xml', '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"><manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>')
        archive.writestr('content.xml', '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2"><office:body><office:spreadsheet><table:table table:name="Bütçe"><table:table-row><table:table-cell office:value-type="string"><text:p>Personel taşıma hizmeti</text:p></table:table-cell></table:table-row></table:table></office:spreadsheet></office:body></office:document-content>')
    assert 'Personel taşıma hizmeti' in read_extended(path)


@pytest.mark.parametrize('extension', ['.docm', '.pptm'])
def test_macro_document_packages_are_read_as_data(tmp_path, extension):
    path = tmp_path / ('report' + extension)
    with zipfile.ZipFile(path, 'w') as archive:
        if extension == '.docm':
            archive.writestr('word/document.xml', '<document><p>Gider değerlendirmesi</p></document>')
            archive.writestr('word/vbaProject.bin', b'ignored-macro-data')
        else:
            archive.writestr('ppt/slides/slide10.xml', '<slide><p>Son değerlendirme</p></slide>')
            archive.writestr('ppt/slides/slide2.xml', '<slide><p>Gider değerlendirmesi</p></slide>')
    text = read_extended(path)
    assert text.startswith('Gider değerlendirmesi')
    assert 'ignored-macro-data' not in text


def test_large_expanded_package_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / 'large.odt'
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('content.xml', '<root>' + 'x' * 2048 + '</root>')
    monkeypatch.setattr('format_readers.MAX_EXPANDED_BYTES', 1024)
    with pytest.raises(ValueError, match='sınırını'):
        read_extended(path)


def test_agent_logs_do_not_pollute_content_but_user_logs_are_read(tmp_path, monkeypatch):
    root = tmp_path / 'documents'
    project = root / 'agent'
    (project / 'logs').mkdir(parents=True)
    (project / 'logs' / 'ollama.log').write_text('Internal generated model output', encoding='utf-8')
    (root / 'meeting.log').write_text('Müşteri toplantısı kararları', encoding='utf-8')
    monkeypatch.setattr('local_catalog.PROJECT_ROOT', project)
    report = rebuild_catalog([root], tmp_path / 'catalog.db')
    assert report['indexed'] == 2
    assert report['content'] == 1
    assert report['generated_name_only'] == 1

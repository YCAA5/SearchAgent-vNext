import json
import tempfile
import time
import traceback
from pathlib import Path


def run_self_test(report_path, verify_model=False, verify_ocr=False):
    report = {'ok': False, 'checks': {}}
    try:
        import customtkinter as ctk
        import pymupdf
        from PIL import Image, ImageDraw, ImageFont
        from docx import Document
        from openpyxl import Workbook
        from app_paths import resource_path
        import desktop_app
        from local_catalog import rebuild_catalog, search_catalog
        from semantic_search import build_semantic_index, semantic_search
        from format_readers import read_image_text
        with tempfile.TemporaryDirectory(prefix='search-agent-check-') as temporary:
            root = Path(temporary)
            documents = root / 'documents'
            documents.mkdir()
            (documents / 'note.md').write_text('Package validation: personnel transport costs and annual budget.', encoding='utf-8')
            with pymupdf.open() as pdf:
                pdf.new_page().insert_text((72, 72), 'Package validation report for personnel transport costs.')
                pdf.save(documents / 'report.pdf')
            workbook = Workbook()
            workbook.active['A1'] = 'Package validation budget'
            workbook.active['B1'] = 1200
            workbook.save(documents / 'budget.xlsx')
            workbook.close()
            document = Document()
            document.add_paragraph('Package validation: personnel services agreement.')
            document.save(documents / 'agreement.docx')
            catalog, vectors = root / 'catalog.db', root / 'vectors.db'
            indexed = rebuild_catalog([documents], catalog)
            assert indexed['content'] == 4, indexed
            report['checks']['readers'] = ['md', 'pdf', 'xlsx', 'docx']
            assert resource_path('assets/app-icon.ico').is_file()
            with Image.open(resource_path('assets/app-icon.ico')) as image:
                assert image.width >= 256
            report['checks']['icon'] = True
            desktop_app.SETTINGS = root / 'preferences.json'
            desktop_app.DATABASE = catalog
            desktop_app.SEMANTIC_DATABASE = vectors
            window = ctk.CTk()
            window.withdraw()
            app = desktop_app.SearchApp(window)
            try:
                assert app.search_button.cget('state') == 'disabled'
                assert app.preparation_banner.winfo_manager() == 'grid'
                report['checks']['preparation_gate'] = True
                app.query.insert('1.0', 'annual personnel transportation spending')
                app.display_results({'results': search_catalog(catalog, 'validation')['results'], 'total_count': 4})
                deadline = time.monotonic() + 20
                while app.preview_payload is None and time.monotonic() < deadline:
                    window.update()
                    time.sleep(0.03)
                selected = app.selected_id
                assert selected is not None
                app.change_language('English')
                app.change_theme('Dark')
                app.change_result_size('Large')
                app.change_result_view('List')
                window.update_idletasks()
                assert app.query.get('1.0', 'end-1c') == 'annual personnel transportation spending'
                assert app.selected_id == selected and app.language == 'en' and app.theme == 'dark'
                assert app.nav_buttons['Arama'].cget('text') == 'Search'
                assert app.badges[selected].cget('width') == 64
                app.change_language('Türkçe')
                app.change_result_size('Küçük')
                app.change_result_view('Kartlar')
                app.change_theme('Açık')
                assert app.nav_buttons['Arama'].cget('text') == 'Arama'
                report['checks']['ui'] = ['tr', 'en', 'light', 'dark', 'small', 'medium', 'large', 'cards', 'list']
            finally:
                app.close()
            if verify_ocr:
                image_path = root / 'ocr.png'
                with Image.new('RGB', (850, 150), 'white') as image:
                    draw = ImageDraw.Draw(image)
                    draw.text((20, 30), 'SEARCH AGENT TEST', fill='black', font=ImageFont.load_default(size=48))
                    image.save(image_path)
                text = read_image_text(image_path)
                assert 'SEARCH' in text.upper(), text
                report['checks']['ocr'] = True
            if verify_model:
                model_report = build_semantic_index(catalog, vectors)
                result = semantic_search(catalog, vectors, 'cost of employees travelling to work')
                assert result['results']
                assert 'transport' in result['results'][0]['snippet'].lower()
                from model_runtime import LocalEmbedder
                report['checks']['runtime'] = [{'model': entry['name'], 'vram_bytes': entry.get('size_vram', 0)} for entry in LocalEmbedder().request('/api/ps').get('models', [])]
                report['checks']['model'] = model_report
        report['ok'] = True
    except Exception:
        report['error'] = traceback.format_exc()
    finally:
        if verify_model:
            from model_runtime import stop_test_servers
            stop_test_servers()
        report_path = Path(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['ok'] else 1

import json
import os
import queue
import sqlite3
import subprocess
import threading
import tkinter as tk
from contextlib import closing
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app_paths import APP_ROOT, DATA_ROOT, resource_path
from i18n import LocalizedVar, translate
from document_preview import document_preview
from local_catalog import rebuild_catalog, search_catalog
from scope_paths import normalize_roots
from preparation import prepare_all, index_status
from semantic_search import build_semantic_index, index_coverage, semantic_search, warm_search
from ui_theme import DARK, LIGHT, color, extension_value, icon, load_preferences, number, save_preferences


PROJECT = APP_ROOT
SETTINGS = DATA_ROOT / 'config' / 'desktop.json'
DATABASE = DATA_ROOT / 'data' / 'indexes' / 'desktop.db'
SEMANTIC_DATABASE = DATA_ROOT / 'data' / 'indexes' / 'semantic.db'
DEFAULT_ROOT = str(Path.home() / 'Documents')
FILE_TYPES = ['Tüm dosyalar', 'PDF', 'DOCX', 'DOCM', 'XLSX', 'XLS', 'XLSM', 'XLSB', 'TXT', 'CSV', 'PPTX', 'PPTM', 'MD', 'JSON', 'XML', 'YAML', 'RTF', 'ODT', 'ODS', 'ODP', 'EPUB', 'EML', 'PY', 'CS', 'JPG', 'PNG', 'WEBP', 'TIF', 'BMP', 'PSD', 'SVG']


class SearchApp:
    def __init__(self, window):
        self.window = window
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.preparing = False
        self.search_busy = False
        self._warm_started = False
        self._model_mismatch = False
        self.ready_status = {'can_search': False, 'current': False}
        self.closed = False
        self.preview_generation = 0
        self.rows, self.cards = {}, {}
        self.selected_id = None
        self.photo = None
        self.preview_payload = None
        self.buttons = []
        self.nav_buttons, self.pages = {}, {}
        self.stat_labels = {}
        self.localized_widgets, self.localized_variables = [], []
        self.size_selectors, self.view_selectors = [], []
        self.badges = {}
        self.settings_error = ''
        try:
            settings = load_preferences(SETTINGS, [DEFAULT_ROOT])
        except (OSError, ValueError) as error:
            settings = {'folders': [DEFAULT_ROOT], 'ocr_images': False, 'theme': 'light'}
            self.settings_error = str(error)
        self.language = os.environ.get('SEARCH_AGENT_LANGUAGE', settings.get('language', 'tr'))
        self.result_size = settings.get('result_size', 'medium')
        self.result_view = settings.get('result_view', 'cards')
        self.theme = settings['theme']
        ctk.set_appearance_mode(self.theme)
        self.ocr_enabled = tk.BooleanVar(master=window, value=settings['ocr_images'])
        self.status = self.localized_var('Dosyadan aklınızda kalanları anlatın. Aynı kelimelerin geçmesi gerekmez.')
        self.coverage = self.localized_var('')
        self.preparation_notice = self.localized_var('Dosyalarınız henüz aramaya hazır değil. Önce seçtiğiniz konumları hazırlayın.')
        self.index_state = self.localized_var('Dizin kontrol ediliyor')
        self.breadcrumb = self.localized_var('Çalışma alanı  /  Arama')
        self.preview_title = tk.StringVar(master=window, value=self.t('Bir dosya seçin'))
        self.preview_details = tk.StringVar(master=window, value=self.t('İlgili metin ve belge görüntüsü burada açılır.'))
        window.title(self.t('Search Agent — İçeriği Hatırlayarak Bul'))
        scale = max(1.0, window._get_window_scaling())
        width = max(1100, min(1480, int(window.winfo_screenwidth() / scale) - 80))
        height = max(760, min(940, int(window.winfo_screenheight() / scale) - 90))
        window.geometry(f'{width}x{height}')
        window.minsize(1100, 760)
        window.configure(fg_color=color('background'))
        window.protocol('WM_DELETE_WINDOW', self.close)
        window.grid_rowconfigure(0, weight=1)
        window.grid_columnconfigure(1, weight=1)
        self.build_sidebar()
        workspace = ctk.CTkFrame(window, fg_color='transparent', corner_radius=0)
        workspace.grid(row=0, column=1, sticky='nsew', padx=26, pady=(20, 14))
        workspace.grid_columnconfigure(0, weight=1)
        workspace.grid_rowconfigure(1, weight=1)
        self.build_topbar(workspace)
        self.page_host = ctk.CTkFrame(workspace, fg_color='transparent')
        self.page_host.grid(row=1, column=0, sticky='nsew', pady=(18, 8))
        self.page_host.grid_rowconfigure(0, weight=1)
        self.page_host.grid_columnconfigure(0, weight=1)
        self.build_search_page()
        self.build_folders_page(settings['folders'])
        self.build_index_page()
        self.build_settings_page()
        self.build_footer(workspace)
        workspace.bind('<Configure>', self.resize_workspace, add='+')
        self.show_page('Arama')
        self.apply_native_colors()
        self.refresh_coverage()
        self.start_warmup()
        if self.settings_error:
            self.status.set(f'Ayarlar okunamadı: {self.settings_error}')
        self.poll_id = window.after(100, self.poll)
        self.icon_after_id = window.after(350, self.apply_application_icon)

    def t(self, text):
        return translate(text, self.language)

    def localized_var(self, value):
        variable = LocalizedVar(self.window, self.t, value)
        self.localized_variables.append(variable)
        return variable

    def label(self, parent, text='', size=13, bold=False, muted=False, localize=True, **kwargs):
        widget = ctk.CTkLabel(parent, text=self.t(text) if localize else text,
                              font=('Segoe UI', size, 'bold' if bold else 'normal'),
                              text_color=color('muted' if muted else 'text'), **kwargs)
        if localize and text and 'textvariable' not in kwargs:
            self.localized_widgets.append((widget, text))
        return widget

    def button(self, parent, text, command, primary=False, image=None, width=140, **kwargs):
        widget = ctk.CTkButton(parent, text=self.t(text), command=command, height=38, width=width, corner_radius=8,
                               font=('Segoe UI', 13, 'bold' if primary else 'normal'),
                               fg_color=color('accent') if primary else 'transparent',
                               hover_color=color('accent_hover') if primary else color('hover'),
                               text_color=color('accent_text') if primary else color('text'),
                               border_width=0 if primary else 1, border_color=color('border'), image=image, **kwargs)
        self.localized_widgets.append((widget, text))
        return widget

    def panel(self, parent, **kwargs):
        return ctk.CTkFrame(parent, fg_color=color('surface'), border_color=color('border'), border_width=1, corner_radius=12, **kwargs)

    def build_sidebar(self):
        sidebar = ctk.CTkFrame(self.window, width=210, corner_radius=0, fg_color=color('sidebar'))
        sidebar.grid(row=0, column=0, sticky='ns')
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(6, weight=1)
        self.brand_icon = icon('brand', 32, primary=True)
        self.label(sidebar, 'Search Agent', 20, True, image=self.brand_icon, compound='left', padx=8).grid(row=0, column=0, padx=16, pady=(28, 30), sticky='w')
        self.nav_icons = {}
        for position, (title, name) in enumerate([('Arama', 'search'), ('Klasörler', 'folder'), ('Dizin durumu', 'layers'), ('Ayarlar', 'settings')], start=1):
            self.nav_icons[title] = icon(name, 21)
            button = ctk.CTkButton(sidebar, text=self.t(title), image=self.nav_icons[title], compound='left', anchor='w',
                                  height=44, corner_radius=9, font=('Segoe UI', 14), text_color=color('text'),
                                  fg_color='transparent', hover_color=color('hover'),
                                  command=lambda page=title: self.show_page(page))
            button.grid(row=position, column=0, padx=12, pady=5, sticky='ew')
            self.nav_buttons[title] = button
            self.localized_widgets.append((button, title))
        self.privacy_icon = icon('monitor', 18)
        self.label(sidebar, 'Yalnızca bu bilgisayarda', 11, muted=True, image=self.privacy_icon, compound='left', padx=6).grid(row=7, column=0, padx=12, pady=24, sticky='w')

    def theme_selector(self, parent):
        selector = ctk.CTkSegmentedButton(parent, values=[self.t('Açık'), self.t('Koyu')], command=self.change_theme, height=32,
                                        fg_color=color('border'), selected_color=color('soft'),
                                        selected_hover_color=color('hover'), unselected_color=color('surface'),
                                        unselected_hover_color=color('hover'), text_color=color('text'),
                                        font=('Segoe UI', 12), dynamic_resizing=False, width=136)
        selector.set(self.t('Koyu' if self.theme == 'dark' else 'Açık'))
        return selector

    def build_topbar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color='transparent')
        bar.grid(row=0, column=0, sticky='ew')
        bar.grid_columnconfigure(0, weight=1)
        self.label(bar, textvariable=self.breadcrumb, size=13, muted=True).grid(row=0, column=0, sticky='w')
        self.ready_pill = self.label(bar, textvariable=self.index_state, size=12, bold=True, fg_color=color('soft'), corner_radius=12, padx=14, height=30)
        self.ready_pill.grid(row=0, column=1, padx=16)
        self.theme_control = self.theme_selector(bar)
        self.theme_control.grid(row=0, column=2)
        self.language_control = self.language_selector(bar)
        self.language_control.grid(row=0, column=3, padx=(10, 0))

    def new_page(self, title):
        page = ctk.CTkFrame(self.page_host, fg_color='transparent')
        page.grid_columnconfigure(0, weight=1)
        self.pages[title] = page
        return page

    def build_search_page(self):
        page = self.new_page('Arama')
        page.grid_rowconfigure(5, weight=1)
        self.label(page, 'Hatırladığını yaz, dosyanı bul.', 28, True).grid(row=0, column=0, sticky='w', pady=(0, 1))
        self.label(page, 'Dosya adını değil, aklında kalan içeriği anlat.', 14, muted=True).grid(row=1, column=0, sticky='w', pady=(0, 16))
        self.preparation_banner = self.panel(page)
        self.preparation_banner.grid(row=2, column=0, sticky='ew', pady=(0, 12))
        self.preparation_banner.grid_columnconfigure(0, weight=1)
        self.label(self.preparation_banner, textvariable=self.preparation_notice, size=13, bold=True, wraplength=700, justify='left').grid(row=0, column=0, sticky='w', padx=14, pady=12)
        prepare = self.button(self.preparation_banner, 'Aramaya hazırla / güncelle', self.prepare_all, primary=True, width=215)
        prepare.grid(row=0, column=1, padx=12, pady=8)
        self.buttons.append(prepare)
        search_card = self.panel(page)
        search_card.grid(row=3, column=0, sticky='ew')
        search_card.grid_columnconfigure(0, weight=1)
        self.query = ctk.CTkTextbox(search_card, height=88, corner_radius=0, border_width=0,
                                   fg_color=color('surface'), text_color=color('text'), font=('Segoe UI', 15),
                                   wrap='word', undo=True, border_spacing=8)
        self.query.grid(row=0, column=0, sticky='ew', padx=10, pady=(10, 0))
        self.query.bind('<Control-Return>', self.search_shortcut)
        self.query.bind('<KeyRelease>', self.update_placeholder, add='+')
        self.query.bind('<FocusIn>', self.update_placeholder, add='+')
        self.query.bind('<FocusOut>', self.update_placeholder, add='+')
        self.placeholder = self.label(search_card, 'Dosyadan hatırladığınız bir bölümü veya kısa özetini yazın…', 14, muted=True)
        self.placeholder.place(x=20, y=17)
        self.placeholder.bind('<Button-1>', lambda event: self.focus_query())
        ctk.CTkFrame(search_card, height=1, fg_color=color('border')).grid(row=1, column=0, padx=18, pady=(3, 8), sticky='ew')
        controls = ctk.CTkFrame(search_card, fg_color='transparent')
        controls.grid(row=2, column=0, padx=16, pady=(0, 13), sticky='ew')
        controls.grid_columnconfigure(1, weight=1)
        self.extension = ctk.CTkComboBox(controls, values=[self.t(FILE_TYPES[0])] + FILE_TYPES[1:], width=150, height=34, state='normal',
                                        fg_color=color('surface'), border_color=color('border'), text_color=color('text'),
                                        button_color=color('border'), button_hover_color=color('hover'),
                                        dropdown_fg_color=color('surface'), dropdown_text_color=color('text'), dropdown_hover_color=color('hover'))
        self.extension.set(self.t('Tüm dosyalar'))
        self.extension.grid(row=0, column=0, sticky='w')
        self.label(controls, 'Ctrl + Enter', 11, muted=True).grid(row=0, column=2, padx=(8, 12))
        self.search_button = self.button(controls, 'İçeriği hatırlayarak bul', self.search, primary=True, width=230)
        self.search_button.grid(row=0, column=3)
        self.buttons.append(self.search_button)
        secondary = ctk.CTkFrame(page, fg_color='transparent')
        secondary.grid(row=4, column=0, sticky='ew', pady=(10, 14))
        secondary.grid_columnconfigure(1, weight=1)
        self.exact_button = self.button(secondary, 'Dosya adıyla ara', self.exact_search_dialog, width=155, image=icon('search', 17))
        self.exact_button.grid(row=0, column=0, sticky='w')
        self.buttons.append(self.exact_button)
        self.label(secondary, textvariable=self.coverage, size=12, muted=True).grid(row=0, column=1, padx=16, sticky='w')
        split = ctk.CTkFrame(page, fg_color='transparent')
        split.grid(row=5, column=0, sticky='nsew')
        split.grid_columnconfigure((0, 1), weight=1, uniform='panels')
        split.grid_rowconfigure(0, weight=1)
        result_panel = self.panel(split)
        result_panel.grid(row=0, column=0, sticky='nsew', padx=(0, 7))
        result_panel.grid_columnconfigure(0, weight=1)
        result_panel.grid_rowconfigure(2, weight=1)
        heading = ctk.CTkFrame(result_panel, fg_color='transparent')
        heading.grid(row=0, column=0, sticky='ew', padx=16, pady=(13, 6))
        heading.grid_columnconfigure(0, weight=1)
        self.label(heading, 'İlgili dosyalar', 20, True).grid(row=0, column=0, sticky='w')
        self.result_count = self.label(heading, '', 12, muted=True)
        self.result_count.grid(row=0, column=1)
        self.make_result_controls(result_panel).grid(row=1, column=0, padx=16, pady=(0, 6), sticky='w')
        self.results = ctk.CTkScrollableFrame(result_panel, fg_color='transparent', corner_radius=0, height=100,
                                             scrollbar_button_color=color('border'), scrollbar_button_hover_color=color('muted'))
        self.results.grid(row=2, column=0, sticky='nsew', padx=7, pady=(0, 8))
        self.results.grid_columnconfigure(0, weight=1)
        self.empty_results = self.label(self.results, 'Aradığınız içerik burada listelenecek.\nBir hatırlama notuyla başlayın.', 13, muted=True, justify='center', wraplength=320)
        self.empty_results.grid(row=0, column=0, pady=70, padx=15)
        self.results.bind('<Configure>', self.resize_cards, add='+')
        preview_panel = self.panel(split)
        preview_panel.grid(row=0, column=1, sticky='nsew', padx=(7, 0))
        self.build_preview(preview_panel)

    def build_preview(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(4, weight=1)
        self.label(parent, 'Önizleme', 20, True).grid(row=0, column=0, padx=16, pady=(13, 6), sticky='w')
        self.title_label = self.label(parent, textvariable=self.preview_title, size=14, bold=True, anchor='w', wraplength=420)
        self.title_label.grid(row=1, column=0, padx=16, sticky='ew')
        self.details_label = self.label(parent, textvariable=self.preview_details, size=11, muted=True, justify='left', anchor='w', wraplength=420)
        self.details_label.grid(row=2, column=0, padx=16, pady=(4, 10), sticky='ew')
        tabs = ctk.CTkFrame(parent, fg_color='transparent')
        tabs.grid(row=3, column=0, padx=12, sticky='ew')
        self.preview_tab_buttons = {}
        for position, (key, title) in enumerate([('text', 'İlgili metin'), ('image', 'Sayfa görünümü')]):
            button = ctk.CTkButton(tabs, text=self.t(title), width=135, height=32, corner_radius=6,
                                  text_color=color('text'), fg_color='transparent', hover_color=color('hover'),
                                  font=('Segoe UI', 12), command=lambda mode=key: self.show_preview_mode(mode))
            button.grid(row=0, column=position, padx=3)
            self.preview_tab_buttons[key] = button
            self.localized_widgets.append((button, title))
        self.preview_host = ctk.CTkFrame(parent, fg_color='transparent')
        self.preview_host.grid(row=4, column=0, padx=12, pady=(7, 8), sticky='nsew')
        self.preview_host.grid_columnconfigure(0, weight=1)
        self.preview_host.grid_rowconfigure(0, weight=1)
        self.preview_text = ctk.CTkTextbox(self.preview_host, fg_color=color('surface'), text_color=color('text'),
                                          font=('Segoe UI', 13), corner_radius=0, wrap='word', height=100, state='disabled')
        self.image_host = ctk.CTkFrame(self.preview_host, fg_color='transparent')
        self.image_host.grid_columnconfigure(0, weight=1)
        self.image_host.grid_rowconfigure(0, weight=1)
        self.preview_image = self.label(self.image_host, self.t('PDF veya resim seçtiğinizde\ngörüntü burada gösterilir.'), 13, muted=True, localize=False)
        self.preview_image.grid(row=0, column=0, sticky='nsew')
        self.page_label = self.label(self.image_host, '', 11, muted=True)
        self.page_label.grid(row=1, column=0, pady=5)
        self.location_button = self.button(parent, 'Klasöründe göster', self.show_location, width=185, image=icon('folder', 18))
        self.location_button.grid(row=5, column=0, padx=16, pady=(0, 14), sticky='w')
        self.location_button.configure(state='disabled')
        self.preview_mode = 'text'
        self.show_preview_mode('text')
        self.preview_host.bind('<Configure>', self.resize_preview, add='+')

    def build_folders_page(self, roots):
        page = self.new_page('Klasörler')
        self.label(page, 'Arama konumları', 28, True).grid(row=0, column=0, sticky='w')
        self.label(page, 'Seçtiğiniz klasörler ve alt klasörleri aranır.', 14, muted=True).grid(row=1, column=0, sticky='w', pady=(4, 22))
        panel = self.panel(page)
        panel.grid(row=2, column=0, sticky='ew')
        panel.grid_columnconfigure(0, weight=1)
        self.folders = tk.Listbox(panel, height=8, font=('Segoe UI', 12), borderwidth=0, highlightthickness=0, activestyle='none', exportselection=False)
        self.folders.grid(row=0, column=0, sticky='ew', padx=20, pady=20)
        for root in normalize_roots(roots):
            self.folders.insert('end', str(root))
        actions = ctk.CTkFrame(page, fg_color='transparent')
        actions.grid(row=3, column=0, sticky='w', pady=16)
        for position, (title, command, primary) in enumerate([('Klasör ekle', self.add_folder, True), ('Seçileni kaldır', self.remove_folder, False), ('Disk / ağ yolu ekle', self.add_shared_folder, False)]):
            button = self.button(actions, title, command, primary=primary)
            button.grid(row=0, column=position, padx=(0, 10))
            self.buttons.append(button)
        self.label(page, 'Konum değiştirdikten sonra Dizin durumu bölümünden dosya ve anlam dizinini yenileyin.', 13, muted=True, wraplength=720, justify='left').grid(row=4, column=0, sticky='w', pady=10)

    def build_index_page(self):
        wrapper = self.new_page('Dizin durumu')
        wrapper.grid_rowconfigure(0, weight=1)
        page = ctk.CTkScrollableFrame(wrapper, fg_color='transparent')
        page.grid(row=0, column=0, sticky='nsew')
        page.grid_columnconfigure(0, weight=1)
        self.label(page, 'Dosyalarınız aramaya hazır mı?', 28, True).grid(row=0, column=0, sticky='w')
        self.label(page, 'Tek düğmeyle dosyaları okuyun ve anlam kayıtlarını hazırlayın.', 14, muted=True).grid(row=1, column=0, sticky='w', pady=(4, 14))
        prepare = self.button(page, 'Aramaya hazırla / güncelle', self.prepare_all, primary=True, width=260)
        prepare.grid(row=2, column=0, sticky='w', pady=(0, 12))
        self.buttons.append(prepare)
        self.label(page, textvariable=self.preparation_notice, size=13, wraplength=760, justify='left').grid(row=3, column=0, sticky='w', pady=(0, 18))
        stats = ctk.CTkFrame(page, fg_color='transparent')
        stats.grid(row=4, column=0, sticky='ew')
        stats.grid_columnconfigure((0, 1, 2), weight=1, uniform='stats')
        for position, (key, title) in enumerate([('files', 'Kayıtlı dosya adı'), ('content', 'İçeriği okunabilen dosya'), ('chunks', 'Hazırlanmış metin bölümü')]):
            panel = self.panel(stats)
            panel.grid(row=0, column=position, sticky='ew', padx=(0, 10), pady=(0, 20))
            self.stat_labels[key] = self.label(panel, '—', 28, True)
            self.stat_labels[key].pack(anchor='w', padx=20, pady=(18, 0))
            self.label(panel, title, 12, muted=True).pack(anchor='w', padx=20, pady=(0, 18))
        self.label(page, 'Hazırlık sırası: konumları kontrol et → dosyaları oku → anlam kayıtlarını güncelle.', 14, wraplength=750, justify='left').grid(row=5, column=0, sticky='w', pady=10)
        self.label(page, 'Durdurursanız son hazır dizin korunur. Aynı düğme hazırlığa devam eder.', 13, muted=True, wraplength=750, justify='left').grid(row=6, column=0, sticky='w', pady=10)
        self.label(page, 'Resim ve 3D dosyalarının görünüşünü henüz anlamaz. OCR yalnızca resimdeki yazıları okur.', 12, muted=True, wraplength=740, justify='left').grid(row=7, column=0, sticky='w', pady=8)

    def build_settings_page(self):
        wrapper = self.new_page('Ayarlar')
        wrapper.grid_rowconfigure(0, weight=1)
        page = ctk.CTkScrollableFrame(wrapper, fg_color='transparent')
        page.grid(row=0, column=0, sticky='nsew')
        page.grid_columnconfigure(0, weight=1)
        self.label(page, 'Size uygun bir çalışma alanı', 28, True).grid(row=0, column=0, sticky='w', pady=(0, 22))
        appearance = self.panel(page)
        appearance.grid(row=1, column=0, sticky='ew', pady=(0, 16))
        self.label(appearance, 'Görünüm', 18, True).pack(anchor='w', padx=20, pady=(18, 2))
        self.label(appearance, 'Tema tercihiniz bir sonraki açılışta da korunur.', 13, muted=True).pack(anchor='w', padx=20)
        self.settings_theme_control = self.theme_selector(appearance)
        self.settings_theme_control.pack(anchor='w', padx=20, pady=18)
        language_panel = self.panel(page)
        language_panel.grid(row=2, column=0, sticky='ew', pady=(0, 16))
        self.label(language_panel, 'Dil', 18, True).pack(anchor='w', padx=20, pady=(18, 8))
        self.settings_language_control = self.language_selector(language_panel)
        self.settings_language_control.pack(anchor='w', padx=20, pady=(0, 18))
        results_panel = self.panel(page)
        results_panel.grid(row=3, column=0, sticky='ew', pady=(0, 16))
        self.label(results_panel, 'Sonuç görünümü', 18, True).pack(anchor='w', padx=20, pady=(18, 8))
        self.make_result_controls(results_panel).pack(anchor='w', padx=20, pady=(0, 18))
        ocr_panel = self.panel(page)
        ocr_panel.grid(row=4, column=0, sticky='ew', pady=(0, 16))
        self.label(ocr_panel, 'Resimlerdeki yazılar', 18, True).pack(anchor='w', padx=20, pady=(18, 4))
        self.ocr_switch = ctk.CTkSwitch(ocr_panel, text=self.t('OCR ile resim yazılarını oku'), variable=self.ocr_enabled,
                                      command=self.ocr_changed, progress_color=color('accent'),
                                      text_color=color('text'), font=('Segoe UI', 13))
        self.ocr_switch.pack(anchor='w', padx=20, pady=12)
        self.buttons.append(self.ocr_switch)
        self.localized_widgets.append((self.ocr_switch, 'OCR ile resim yazılarını oku'))
        self.label(ocr_panel, 'Bu seçenek daha yavaştır. Değiştirdikten sonra dosya ve anlam dizinlerini yenileyin.', 13, muted=True, wraplength=720, justify='left').pack(anchor='w', padx=20, pady=(0, 18))
        privacy = self.panel(page)
        privacy.grid(row=5, column=0, sticky='ew')
        self.label(privacy, 'Bilgisayarınızda çalışır', 18, True).pack(anchor='w', padx=20, pady=(18, 6))
        self.label(privacy, 'Anlamsal arama: Qwen3-Embedding-0.6B\nResim yazıları: Tesseract OCR\nBelgeleriniz yerel dizinde işlenir; arama için bir bulut servisine gönderilmez.', 13, muted=True, justify='left').pack(anchor='w', padx=20, pady=(0, 18))

    def build_footer(self, parent):
        footer = ctk.CTkFrame(parent, fg_color='transparent')
        footer.grid(row=2, column=0, sticky='ew')
        footer.grid_columnconfigure(0, weight=1)
        self.progress = ctk.CTkProgressBar(footer, mode='indeterminate', height=3, progress_color=color('accent'), fg_color=color('border'))
        self.progress.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 7))
        self.progress.grid_remove()
        self.status_label = self.label(footer, textvariable=self.status, size=11, muted=True, justify='left', anchor='w', wraplength=870)
        self.status_label.grid(row=1, column=0, sticky='ew')
        self.stop_button = self.button(footer, 'Durdur', self.cancel.set, width=90)
        self.stop_button.grid(row=1, column=1, padx=(10, 0))
        self.stop_button.grid_remove()

    def show_page(self, title):
        for name, page in self.pages.items():
            page.grid_remove()
        self.pages[title].grid(row=0, column=0, sticky='nsew')
        for name, button in self.nav_buttons.items():
            button.configure(fg_color=color('soft') if name == title else 'transparent', font=('Segoe UI', 14, 'bold' if name == title else 'normal'))
        self.breadcrumb.set(f'Çalışma alanı  /  {title}')
        self.active_page = title
        if title == 'Dizin durumu':
            self.refresh_coverage()

    def apply_native_colors(self):
        palette = DARK if self.theme == 'dark' else LIGHT
        self.folders.configure(bg=palette['surface'], fg=palette['text'], selectbackground=palette['accent'], selectforeground=palette['accent_text'])
        self.preview_text.tag_config('match', background=palette['highlight'], foreground=palette['highlight_text'])

    def change_theme(self, value):
        self.theme = 'dark' if value in {'Koyu', 'Dark'} else 'light'
        ctk.set_appearance_mode(self.theme)
        theme_label = self.t('Koyu' if self.theme == 'dark' else 'Açık')
        self.theme_control.set(theme_label)
        self.settings_theme_control.set(theme_label)
        self.apply_native_colors()
        self.persist_settings()


    def apply_application_icon(self):
        path = resource_path('assets/app-icon.ico')
        if path.is_file() and not self.closed:
            self.window.iconbitmap(str(path))

    def language_selector(self, parent):
        selector = ctk.CTkOptionMenu(parent, values=['Türkçe', 'English'], command=self.change_language,
                                    width=110, height=32, fg_color=color('surface'), text_color=color('text'),
                                    button_color=color('border'), button_hover_color=color('hover'),
                                    dropdown_fg_color=color('surface'), dropdown_text_color=color('text'))
        selector.set('English' if self.language == 'en' else 'Türkçe')
        return selector

    def change_language(self, value):
        self.language = 'en' if value == 'English' else 'tr'
        alive = []
        for widget, source in self.localized_widgets:
            if widget.winfo_exists():
                widget.configure(text=self.t(source))
                alive.append((widget, source))
        self.localized_widgets = alive
        for variable in self.localized_variables:
            variable.refresh()
        self.window.title(self.t('Search Agent — İçeriği Hatırlayarak Bul'))
        for selector in (self.theme_control, self.settings_theme_control):
            selector.configure(values=[self.t('Açık'), self.t('Koyu')])
            selector.set(self.t('Koyu' if self.theme == 'dark' else 'Açık'))
        for selector in (self.language_control, self.settings_language_control):
            selector.set(value)
        current_filter = self.extension.get()
        self.extension.configure(values=[self.t(FILE_TYPES[0])] + FILE_TYPES[1:])
        if current_filter in {'Tüm dosyalar', 'All files'}:
            self.extension.set(self.t(FILE_TYPES[0]))
        self.update_result_controls()
        self.redraw_result_cards()
        if self.selected_id is None:
            self.preview_title.set(self.t('Bir dosya seçin'))
            self.preview_details.set(self.t('İlgili metin ve belge görüntüsü burada açılır.'))
        if self.photo is None:
            self.preview_image.configure(text=self.t('PDF veya resim seçtiğinizde\ngörüntü burada gösterilir.'))
        if self.preview_payload and self.preview_payload['page']:
            self.page_label.configure(text=self.t(f"Sayfa {self.preview_payload['page']} / {self.preview_payload['pages']}"))
        if self.persist_settings():
            self.status.set('Dil tercihiniz kaydedildi.')

    def make_result_controls(self, parent):
        frame = ctk.CTkFrame(parent, fg_color='transparent')
        size = ctk.CTkSegmentedButton(frame, values=[self.t(name) for name in ('Küçük', 'Orta', 'Büyük')],
                                     command=self.change_result_size, height=28, width=175, dynamic_resizing=False,
                                     fg_color=color('border'), selected_color=color('soft'), selected_hover_color=color('hover'),
                                     unselected_color=color('surface'), unselected_hover_color=color('hover'),
                                     text_color=color('text'), font=('Segoe UI', 11))
        size.grid(row=0, column=0, padx=(0, 8))
        view = ctk.CTkOptionMenu(frame, values=[self.t('Kartlar'), self.t('Liste')], command=self.change_result_view,
                               width=100, height=28, fg_color=color('surface'), text_color=color('text'),
                               button_color=color('border'), button_hover_color=color('hover'),
                               dropdown_fg_color=color('surface'), dropdown_text_color=color('text'), font=('Segoe UI', 11))
        view.grid(row=0, column=1)
        self.size_selectors.append(size)
        self.view_selectors.append(view)
        self.update_result_controls()
        return frame

    def update_result_controls(self):
        label = {'small': 'Küçük', 'medium': 'Orta', 'large': 'Büyük'}[self.result_size]
        for selector in self.size_selectors:
            selector.configure(values=[self.t(name) for name in ('Küçük', 'Orta', 'Büyük')])
            selector.set(self.t(label))
        for selector in self.view_selectors:
            selector.configure(values=[self.t('Kartlar'), self.t('Liste')])
            selector.set(self.t('Liste' if self.result_view == 'list' else 'Kartlar'))

    def result_style(self):
        return {
            'small': {'icon': 28, 'badge_font': 8, 'title': 13, 'body': 11, 'padding': 10},
            'medium': {'icon': 42, 'badge_font': 10, 'title': 14, 'body': 12, 'padding': 18},
            'large': {'icon': 64, 'badge_font': 13, 'title': 16, 'body': 13, 'padding': 22},
        }[self.result_size]

    def change_result_size(self, value):
        self.result_size = {'Küçük': 'small', 'Small': 'small', 'Orta': 'medium', 'Medium': 'medium', 'Büyük': 'large', 'Large': 'large'}[value]
        self.update_result_controls()
        self.redraw_result_cards()
        self.persist_settings()

    def change_result_view(self, value):
        self.result_view = 'list' if value in {'Liste', 'List'} else 'cards'
        self.update_result_controls()
        self.redraw_result_cards()
        self.persist_settings()

    def redraw_result_cards(self):
        if not self.rows:
            return
        for child in self.results.winfo_children():
            child.destroy()
        self.cards.clear()
        self.badges.clear()
        for position, (item, row) in enumerate(self.rows.items()):
            self.create_result_card(item, row, position)
        for item, (card, *labels) in self.cards.items():
            selected = item == self.selected_id
            card.configure(fg_color=color('soft') if selected else color('surface'),
                           border_color=color('accent') if selected else color('border'))
        self.result_count.configure(text=self.t(f'{len(self.rows)} aday'))

    def save_settings(self):
        save_preferences(SETTINGS, {'folders': list(self.folders.get(0, 'end')), 'ocr_images': self.ocr_enabled.get(), 'theme': self.theme, 'language': self.language, 'result_size': self.result_size, 'result_view': self.result_view})

    def persist_settings(self):
        try:
            self.save_settings()
            return True
        except (OSError, ValueError) as error:
            self.status.set(f'Tercihler kaydedilemedi: {error}')
            return False

    def ocr_changed(self):
        self.persist_settings()
        self.status.set('OCR tercihi değişti. Dosya dizinini, ardından anlam dizinini yenileyin.')
        self.refresh_coverage()

    def refresh_coverage(self):
        try:
            coverage = index_coverage(DATABASE)
            self.coverage.set(f"{number(coverage['content'])} dosyanın içeriği hazır")
            for key in ('files', 'content'):
                if key in self.stat_labels:
                    self.stat_labels[key].configure(text=number(coverage[key]))
            self.ready_status = index_status(DATABASE, SEMANTIC_DATABASE, list(self.folders.get(0, 'end')), self.ocr_enabled.get())
            if self._model_mismatch:
                self.ready_status.update(can_search=False, current=False, reason='model')
            ready = self.ready_status['can_search']
            self.stat_labels.get('chunks', self.result_count).configure(text=number(self.ready_status['chunks']))
            if self.ready_status['current']:
                self.index_state.set('Dizin hazır')
                self.preparation_banner.grid_remove()
            else:
                self.index_state.set('Güncelleme gerekiyor' if ready else 'Hazırlık gerekiyor')
                reason = self.ready_status['reason']
                self.preparation_notice.set(
                    'Model değişmiş. Anlam dizinini yeniden hazırlayın.' if reason == 'model' else
                    'Bazı konumlar çevrimdışı. Son hazır kayıtlarda arayabilirsiniz.' if reason == 'offline' else
                    'Son hazır kayıtlarda arayabilirsiniz. Yeni içerikler için hazırlığı güncelleyin.' if ready else
                    'Dosyalarınız henüz aramaya hazır değil. Önce seçtiğiniz konumları hazırlayın.')
                self.preparation_banner.grid()
            if not self.search_busy:
                self.search_button.configure(state='normal' if ready and (not self.busy or self.preparing) else 'disabled')
        except (OSError, ValueError, sqlite3.Error):
            self.index_state.set('Hazırlık gerekiyor')
            self.ready_status = {'can_search': False, 'current': False}
            self.preparation_banner.grid()

    def start_warmup(self):
        if self._warm_started or not self.ready_status.get('can_search'):
            return
        self._warm_started = True
        def worker():
            try:
                warm_search(DATABASE, SEMANTIC_DATABASE)
                self.events.put(('warm_ready', ''))
            except Exception as error:
                self.events.put(('warm_ready', str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def prepare_all(self):
        if self.busy:
            return
        roots = list(self.folders.get(0, 'end'))
        if not roots:
            self.show_page('Klasörler')
            self.status.set('Önce Klasörler bölümünden en az bir konum ekleyin.')
            return
        if not self.persist_settings():
            return
        ocr = self.ocr_enabled.get()
        self.preparing = True
        self.preparation_notice.set('Hazırlık sürüyor; tamamlanan kayıtlar korunur.')
        self.start_task('prepare', lambda: prepare_all(roots, DATABASE, SEMANTIC_DATABASE,
            lambda value: self.events.put(('prepare_progress', value)), self.cancel, ocr),
            'Dosyalar okunuyor…')

    def focus_query(self):
        self.placeholder.place_forget()
        self.query.focus_set()

    def resize_workspace(self, event=None):
        if event is not None:
            self.status_label.configure(wraplength=max(250, event.width - 130))

    def update_placeholder(self, event=None):
        if self.query.get('1.0', 'end-1c').strip():
            self.placeholder.place_forget()
        elif self.window.focus_get() is None or event is None or event.type == tk.EventType.FocusOut:
            self.placeholder.place(x=20, y=17)
        else:
            self.placeholder.place_forget()

    def search_shortcut(self, event=None):
        self.search()
        return 'break'

    def exact_search_dialog(self):
        if self.busy:
            return
        dialog = ctk.CTkToplevel(self.window)
        dialog.title(self.t('Dosya adı / tam kelime araması'))
        dialog.geometry('560x250')
        dialog.transient(self.window)
        dialog.configure(fg_color=color('background'))
        self.label(dialog, 'Dosya adı veya tam kelimeyle ara', 19, True).pack(anchor='w', padx=24, pady=(20, 10))
        entry = ctk.CTkEntry(dialog, height=38, fg_color=color('surface'), text_color=color('text'), border_color=color('border'))
        entry.pack(fill='x', padx=24)
        mode = ctk.CTkOptionMenu(dialog, values=[self.t('Dosya adı'), self.t('Tam kelime')], fg_color=color('surface'), button_color=color('border'), button_hover_color=color('hover'), text_color=color('text'), dropdown_fg_color=color('surface'), dropdown_text_color=color('text'))
        mode.pack(anchor='w', padx=24, pady=12)
        def run(event=None):
            if self.busy or not entry.get().strip():
                return
            query = entry.get()
            search_mode = 'Dosya adı' if mode.get() in {'Dosya adı', 'File name'} else 'İçerik ve ad'
            extension = extension_value(self.extension.get())
            dialog.destroy()
            self.show_page('Arama')
            self.start_task('search', lambda: search_catalog(DATABASE, query, search_mode, extension), 'Dosya adları / kelimeler aranıyor…')
        self.button(dialog, 'Ara', run, primary=True).pack(anchor='e', padx=24, pady=6)
        entry.bind('<Return>', run)
        dialog.after(150, entry.focus_set)

    def add_scope_path(self, value):
        if not value or not value.strip():
            return
        roots = [str(root) for root in normalize_roots([*self.folders.get(0, 'end'), value.strip()])]
        self.folders.delete(0, 'end')
        for root in roots:
            self.folders.insert('end', root)
        self.settings_changed()

    def add_folder(self):
        root = filedialog.askdirectory(parent=self.window, title=self.t('Aranacak klasörü seçin'))
        if root:
            self.add_scope_path(root)

    def add_shared_folder(self):
        dialog = ctk.CTkInputDialog(title=self.t('Disk veya ağ konumu'), text=self.t('Tam klasör yolu veya UNC ağ yolu girin:'))
        self.add_scope_path(dialog.get_input())

    def remove_folder(self):
        for selected in reversed(self.folders.curselection()):
            self.folders.delete(selected)
        self.settings_changed()

    def settings_changed(self):
        self.persist_settings()
        self.status.set('Arama konumları değişti. Dosya ve anlam dizinlerini yenileyin.')
        self.refresh_coverage()

    def start_task(self, kind, function, message):
        if self.busy:
            if kind != 'search' or not self.preparing or self.search_busy:
                return
            self.search_busy = True
            self.search_button.configure(state='disabled')
            def search_worker():
                try:
                    self.events.put(('background_search', function()))
                except Exception as error:
                    self.events.put(('search_error', str(error)))
            threading.Thread(target=search_worker, daemon=True).start()
            return
        self.busy = True
        self.cancel.clear()
        for button in self.buttons:
            button.configure(state='disabled')
        if self.preparing and self.ready_status.get('can_search'):
            self.search_button.configure(state='normal')
        self.stop_button.configure(state='normal' if kind != 'search' else 'disabled')
        self.stop_button.grid()
        self.progress.grid()
        self.progress.start()
        self.status.set(message)
        def worker():
            try:
                self.events.put((kind, function()))
            except Exception as error:
                self.events.put(('error', str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def scan(self):
        if self.busy:
            return
        roots = list(self.folders.get(0, 'end'))
        if not roots:
            self.status.set('Önce Klasörler bölümünden en az bir konum ekleyin.')
            return
        try:
            self.save_settings()
        except (OSError, ValueError) as error:
            self.status.set(f'Ayarlar kaydedilemedi: {error}')
            return
        ocr = self.ocr_enabled.get()
        self.start_task('scan', lambda: rebuild_catalog(roots, DATABASE, lambda count, path: self.events.put(('progress', f'{number(count)} dosya okundu…')), self.cancel, ocr=ocr), 'Dosyalar okunuyor…')

    def prepare_semantic(self):
        self.start_task('semantic', lambda: build_semantic_index(DATABASE, SEMANTIC_DATABASE,
            lambda done, total, name: self.events.put(('progress', f'Anlam kayıtları: {done}/{total} • {name}')), self.cancel), 'İçerikler aramaya hazırlanıyor…')

    def finish_task(self):
        self.busy = False
        self.preparing = False
        self.progress.stop()
        self.progress.grid_remove()
        self.stop_button.grid_remove()
        for button in self.buttons:
            button.configure(state='normal')
        self.refresh_coverage()

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'warm_ready':
                    if value:
                        self.status.set(value)
                        if value == 'Model değişmiş. Anlam dizinini yeniden hazırlayın.':
                            self._model_mismatch = True
                            self.refresh_coverage()
                    continue
                if kind in {'background_search', 'search_error'}:
                    self.search_busy = False
                    self.refresh_coverage()
                    if kind == 'background_search':
                        self.display_results(value)
                    else:
                        self.status.set(value)
                    continue
                if kind == 'prepare_progress':
                    stage = self.t('Dosyalar okunuyor…' if value['stage'] == 'scan' else 'İçerikler aramaya hazırlanıyor…')
                    counts = f"{value['done']}/{value['total']}" if value['total'] else str(value['done'])
                    text = f"{stage}  {counts}  ·  {int(value['elapsed'])} s"
                    if value['eta'] is not None:
                        text += f"  ·  ~{int(value['eta'])} s"
                    self.preparation_notice.set(text)
                    self.status.set(text)
                    continue
                if kind == 'progress':
                    self.status.set(value)
                    continue
                if kind in {'preview', 'preview_error'}:
                    generation, payload = value
                    if generation == self.preview_generation:
                        self.display_preview(payload) if kind == 'preview' else self.set_preview_text(payload)
                    continue
                self.finish_task()
                if kind == 'scan':
                    self.refresh_coverage()
                    self.index_state.set('Anlam dizinini yenileyin')
                    self.status.set(f"{number(value['content'])} dosyanın içeriği okundu. Anlam dizinini hazırlayın. {len(value['errors'])} uyarı.")
                    try:
                        (DATABASE.parent / 'last_scan.json').write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
                    except OSError as error:
                        self.status.set(f'Tarama tamamlandı; rapor yazılamadı: {error}')
                elif kind == 'prepare':
                    self._model_mismatch = False
                    self.refresh_coverage()
                    self.start_warmup()
                    if value['scan']['unavailable_roots']:
                        self.status.set('Bazı konumlar çevrimdışı. Son hazır kayıtlarda arayabilirsiniz.')
                    else:
                        self.status.set(f"Aramaya hazır: {number(value['semantic']['documents'])} dosya, {number(value['semantic']['chunks'])} metin bölümü.")
                elif kind == 'semantic':
                    self.refresh_coverage()
                    self.status.set(f"Aramaya hazır: {number(value['documents'])} dosya, {number(value['chunks'])} metin bölümü.")
                elif kind == 'search':
                    self.display_results(value)
                else:
                    self.status.set(value)
        except queue.Empty:
            pass
        self.poll_id = self.window.after(100, self.poll)

    def search(self):
        if self.busy and not (getattr(self, 'preparing', False) and self.ready_status.get('can_search')):
            return
        if hasattr(self, 'ready_status') and not self.ready_status.get('can_search'):
            self.show_page('Dizin durumu')
            self.status.set('Dosyalarınız henüz aramaya hazır değil. Önce seçtiğiniz konumları hazırlayın.')
            return
        query = self.query.get('1.0', 'end-1c')
        extension = extension_value(self.extension.get())
        if not query.strip():
            self.status.set('Dosyadan hatırladığınız bir bölümü veya kısa özetini yazın.')
            return
        scopes = list(self.folders.get(0, 'end')) if hasattr(self, 'folders') else None
        def run_search():
            if scopes is not None:
                result = semantic_search(DATABASE, SEMANTIC_DATABASE, query, extension, allow_stale=True, roots=scopes)
            else:
                result = semantic_search(DATABASE, SEMANTIC_DATABASE, query, extension)
            result['semantic'] = True
            return result
        self.start_task('search', run_search, 'Hatırladığınız içeriğe yakın dosyalar aranıyor…')

    def display_results(self, found):
        self.preview_generation += 1
        for child in self.results.winfo_children():
            child.destroy()
        self.rows.clear()
        self.cards.clear()
        self.badges.clear()
        self.selected_id = None
        self.reset_preview()
        for position, row in enumerate(found['results']):
            item = str(position)
            self.rows[item] = row
            self.create_result_card(item, row, position)
        self.result_count.configure(text=self.t(f"{len(found['results'])} aday"))
        if not self.rows:
            self.label(self.results, 'Bu aramada sonuç bulunamadı.\nBaşka bir ayrıntıyı anlatarak tekrar deneyin.', 13, muted=True, wraplength=330).grid(row=0, column=0, padx=12, pady=50)
        if found.get('semantic'):
            self.status.set(f"İçeriğinize en yakın {len(found['results'])} aday. İlgili bölümü önizlemede kontrol edin; benzerlik kesinlik yüzdesi değildir.")
        else:
            self.status.set(f"{number(found['total_count'])} sonuç bulundu; ilk 200 sonuç gösterilir.")
        if found.get('stale'):
            self.status.set('Son hazır kayıtlarda arıyorsunuz. Yeni içerikler için hazırlığı güncelleyin.')
        if self.rows:
            self.select_result(next(iter(self.rows)))

    def create_result_card(self, item, row, position):
        card = ctk.CTkFrame(self.results, fg_color=color('surface'), border_color=color('border'), border_width=1, corner_radius=10)
        card.grid(row=position, column=0, sticky='ew', padx=2, pady=5)
        card.grid_columnconfigure(1, weight=1)
        style = self.result_style()
        extension = row['file_type'].lstrip('.').upper() or ('FILE' if self.language == 'en' else 'DOSYA')
        badge_color = '#CF493D' if extension == 'PDF' else '#21865B' if extension in {'XLSX', 'XLS', 'CSV', 'ODS'} else '#3472C0' if extension in {'DOCX', 'DOCM', 'ODT'} else '#68758C'
        badge = ctk.CTkLabel(card, text=extension[:4], width=style['icon'], height=style['icon'] + 6, corner_radius=5, fg_color=badge_color, text_color='#FFFFFF', font=('Segoe UI', style['badge_font'], 'bold'))
        self.badges[item] = badge
        badge.grid(row=0, column=0, rowspan=3, padx=(14, 12), pady=style['padding'], sticky='n')
        width = max(180, self.results.winfo_width() - style['icon'] - 74)
        title = self.label(card, row['file_name'], style['title'], True, anchor='w', wraplength=width, justify='left', localize=False)
        title.grid(row=0, column=1, sticky='ew', padx=(0, 12), pady=(12, 3))
        excerpt = row.get('snippet', '').replace('<mark>', '').replace('</mark>', '')
        excerpt = ' '.join(excerpt.split())
        excerpt = excerpt[:155] + ('…' if len(excerpt) > 155 else '')
        snippet = self.label(card, excerpt or self.t('Dosya adıyla bulundu; içerik önizlemesini seçerek açın.'), style['body'], anchor='w', wraplength=width, justify='left', localize=False)
        if self.result_view == 'cards':
            snippet.grid(row=1, column=1, sticky='ew', padx=(0, 12))
        parent_name = Path(row['file_path']).parent.name
        metadata = self.label(card, parent_name + '  •  ' + extension, 11, muted=True, anchor='w', wraplength=width, justify='left', localize=False)
        metadata.grid(row=2, column=1, sticky='ew', padx=(0, 12), pady=(7, 12))
        for widget in (card, badge, title, snippet, metadata):
            widget.bind('<Button-1>', lambda event, selected=item: self.select_result(selected), add='+')
            widget.bind('<Double-Button-1>', lambda event, selected=item: self.open_card_location(selected), add='+')
        self.cards[item] = (card, title, snippet, metadata)

    def resize_cards(self, event=None):
        width = max(180, self.results.winfo_width() - self.result_style()['icon'] - 74)
        for card, title, snippet, metadata in self.cards.values():
            for label in (title, snippet, metadata):
                label.configure(wraplength=width)

    def select_result(self, item):
        if item not in self.rows:
            return
        self.selected_id = item
        for key, (card, *labels) in self.cards.items():
            card.configure(fg_color=color('soft') if key == item else color('surface'), border_color=color('accent') if key == item else color('border'))
        self.preview()

    def open_card_location(self, item):
        self.select_result(item)
        self.show_location()

    def set_preview_text(self, text, match=''):
        self.preview_text.configure(state='normal')
        self.preview_text.delete('1.0', 'end')
        self.preview_text.insert('1.0', text)
        if match:
            position = text.find(match)
            if position >= 0:
                self.preview_text.tag_add('match', f'1.0+{position}c', f'1.0+{position + len(match)}c')
                self.preview_text.see(f'1.0+{position}c')
        self.preview_text.configure(state='disabled')

    def reset_preview(self):
        self.photo = None
        self.preview_payload = None
        self.preview_image.configure(image=None, text=self.t('PDF veya resim seçtiğinizde\ngörüntü burada gösterilir.'))
        self.page_label.configure(text='')
        self.preview_title.set(self.t('Bir dosya seçin'))
        self.preview_details.set(self.t('İlgili metin ve belge görüntüsü burada açılır.'))
        self.location_button.configure(state='disabled')
        self.set_preview_text('')
        self.show_preview_mode('text')

    def show_preview_mode(self, mode):
        self.preview_mode = mode
        self.preview_text.grid_remove()
        self.image_host.grid_remove()
        target = self.preview_text if mode == 'text' else self.image_host
        target.grid(row=0, column=0, sticky='nsew')
        for key, button in self.preview_tab_buttons.items():
            button.configure(fg_color=color('soft') if key == mode else 'transparent')
        if mode == 'image':
            self.render_preview_image()

    def preview(self, event=None):
        if self.selected_id not in self.rows:
            return
        row = self.rows[self.selected_id]
        self.preview_generation += 1
        generation = self.preview_generation
        self.reset_preview()
        self.preview_title.set(row['file_name'])
        self.preview_details.set(row['file_path'])
        self.set_preview_text(self.t('Önizleme hazırlanıyor…'))
        def worker():
            try:
                result = document_preview(DATABASE, row['file_path'], row.get('match_start'), row.get('snippet', ''), width=1000, height=1000)
                result['match'] = row.get('snippet', '').replace('<mark>', '').replace('</mark>', '')
                self.events.put(('preview', (generation, result)))
            except Exception as error:
                self.events.put(('preview_error', (generation, str(error))))
        threading.Thread(target=worker, daemon=True).start()

    def display_preview(self, payload):
        document = payload['document']
        self.preview_payload = payload
        self.preview_title.set(document['file_name'])
        modified = (document.get('modified_at') or '')[:10]
        self.preview_details.set(f"{document['file_path']}\n{document['file_size'] / 1024:,.1f} KB  •  {modified}" + (f"\n{payload['notice']}" if payload['notice'] else ''))
        self.location_button.configure(state='normal')
        self.set_preview_text(payload['text'] if document['content'] else self.t(payload['text']), payload.get('match', ''))
        if payload['image'] is not None:
            if payload['page']:
                self.page_label.configure(text=self.t(f"Sayfa {payload['page']} / {payload['pages']}"))
            if not document['content']:
                self.show_preview_mode('image')
            self.render_preview_image()

    def resize_preview(self, event=None):
        width = max(200, self.preview_host.winfo_width())
        self.title_label.configure(wraplength=width)
        self.details_label.configure(wraplength=width)
        self.render_preview_image()

    def render_preview_image(self):
        if not self.preview_payload or self.preview_payload['image'] is None or self.preview_mode != 'image':
            return
        image = self.preview_payload['image']
        width = max(100, self.preview_host.winfo_width() - 12)
        height = max(100, self.preview_host.winfo_height() - 36)
        scale = min(width / image.width, height / image.height, 1)
        size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        if self.photo is None:
            self.photo = ctk.CTkImage(light_image=image, dark_image=image, size=size)
            self.preview_image.configure(image=self.photo, text='')
        elif self.photo.cget('size') != size:
            self.photo.configure(size=size)

    def show_location(self):
        if self.selected_id not in self.rows:
            return
        path = Path(self.rows[self.selected_id]['file_path'])
        if not path.is_file():
            self.status.set('Dosya taşınmış veya silinmiş olabilir. Dosya dizinini yenileyin.')
            return
        subprocess.Popen(['explorer.exe', '/select,', str(path)])

    def close(self):
        if self.busy:
            self.cancel.set()
            self.status.set('İşlem durduruluyor; tamamlanınca pencereyi tekrar kapatabilirsiniz.')
            return
        self.closed = True
        self.window.after_cancel(self.poll_id)
        self.window.after_cancel(self.icon_after_id)
        self.window.destroy()


def main():
    window = ctk.CTk()
    SearchApp(window)
    window.mainloop()


if __name__ == '__main__':
    main()

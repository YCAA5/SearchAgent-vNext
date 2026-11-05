import re
import tkinter as tk


EN = {
    'Arama': 'Search', 'Klasörler': 'Folders', 'Dizin durumu': 'Index status', 'Ayarlar': 'Settings',
    'Açık': 'Light', 'Koyu': 'Dark', 'Durdur': 'Stop', 'Ara': 'Search', 'Görünüm': 'Appearance',
    'Küçük': 'Small', 'Orta': 'Medium', 'Büyük': 'Large', 'Kartlar': 'Cards', 'Liste': 'List',
    'Dil': 'Language', 'Sonuç simgeleri': 'Result icons', 'Sonuç görünümü': 'Result layout',
    'Simge boyutu': 'Icon size', 'Kayıtlı dosya adı': 'Indexed file names',
    'İçeriği okunabilen dosya': 'Files with readable content', 'Hazırlanmış metin bölümü': 'Prepared text passages',
    'Search Agent — İçeriği Hatırlayarak Bul': 'Search Agent — Find Files by Meaning',
    'Hatırladığını yaz, dosyanı bul.': 'Describe what you remember. Find your file.',
    'Dosya adını değil, aklında kalan içeriği anlat.': 'Describe the content you remember, not the file name.',
    'Dosyadan aklınızda kalanları anlatın. Aynı kelimelerin geçmesi gerekmez.': 'Describe what you remember. The exact words do not have to match.',
    'Dosyadan hatırladığınız bir bölümü veya kısa özetini yazın.': 'Enter a remembered passage or a short summary of the file.',
    'Dosyadan hatırladığınız bir bölümü veya kısa özetini yazın…': 'Describe a passage or write a short summary of the file…',
    'İçeriği hatırlayarak bul': 'Find by remembered content', 'Tüm dosyalar': 'All files',
    'Dosya adıyla ara': 'Search by file name', 'İlgili dosyalar': 'Related files', 'Önizleme': 'Preview',
    'Bir dosya seçin': 'Select a file', 'İlgili metin ve belge görüntüsü burada açılır.': 'The relevant passage and document preview appear here.',
    'İlgili metin': 'Relevant text', 'Sayfa görünümü': 'Page view', 'Klasöründe göster': 'Show in folder',
    'Aradığınız içerik burada listelenecek.\nBir hatırlama notuyla başlayın.': 'Matching files will appear here.\nStart with something you remember.',
    'PDF veya resim seçtiğinizde\ngörüntü burada gösterilir.': 'Select a PDF or image\nto see its preview here.',
    'Arama konumları': 'Search locations', 'Seçtiğiniz klasörler ve alt klasörleri aranır.': 'Search includes your selected folders and their subfolders.',
    'Klasör ekle': 'Add folder', 'Seçileni kaldır': 'Remove selected', 'Yalnızca bu bilgisayarda': 'Only on this computer',
    'Konum değiştirdikten sonra Dizin durumu bölümünden dosya ve anlam dizinini yenileyin.': 'After changing locations, refresh both indexes from Index status.',
    'Dosyalarınız aramaya hazır mı?': 'Are your files ready to search?',
    'Yeni veya değişen içerikler için iki hazırlık adımını tamamlayın.': 'Complete both preparation steps for new or changed content.',
    '1. Dosyaları oku': '1. Read your files',
    'Dosya adlarını, metinleri ve seçiliyse resim yazılarını günceller.': 'Updates file names, document text and, if enabled, text found in images.',
    'Dosya dizinini yenile': 'Refresh file index', '2. Anlam kayıtlarını hazırla': '2. Prepare semantic records',
    'Okunan içerikleri betimleyerek aramaya hazırlar. Değişmeyen kayıtlar tekrar kullanılır.': 'Prepares content for descriptive search. Unchanged records are reused.',
    'Anlam dizinini hazırla': 'Prepare semantic index',
    'Resim ve 3D dosyalarının görünüşünü henüz anlamaz. OCR yalnızca resimdeki yazıları okur.': 'Visual understanding of images and 3D shapes is not included. OCR reads text in images only.',
    'Size uygun bir çalışma alanı': 'Make this workspace your own',
    'Tema tercihiniz bir sonraki açılışta da korunur.': 'Your appearance preference is remembered for next time.',
    'Resimlerdeki yazılar': 'Text in images', 'OCR ile resim yazılarını oku': 'Read text in images with OCR',
    'Bu seçenek daha yavaştır. Değiştirdikten sonra dosya ve anlam dizinlerini yenileyin.': 'This option is slower. Refresh both indexes after changing it.',
    'Bilgisayarınızda çalışır': 'Runs on your computer',
    'Anlamsal arama: Qwen3-Embedding-0.6B\nResim yazıları: Tesseract OCR\nBelgeleriniz yerel dizinde işlenir; arama için bir bulut servisine gönderilmez.': 'Semantic search: Qwen3-Embedding-0.6B\nImage text: Tesseract OCR\nYour documents are processed locally, not sent to a cloud search service.',
    'Dizin kontrol ediliyor': 'Checking index', 'Dizin hazır': 'Index ready', 'Hazırlık gerekiyor': 'Preparation needed',
    'Hazırlık sürüyor': 'Preparing index', 'Dizin bilgisi şu an okunamıyor': 'Index information is currently unavailable',
    'Anlam dizinini yenileyin': 'Refresh semantic index',
    'OCR tercihi değişti. Dosya dizinini, ardından anlam dizinini yenileyin.': 'OCR preference changed. Refresh the file index, then the semantic index.',
    'Arama konumları değişti. Dosya ve anlam dizinlerini yenileyin.': 'Search locations changed. Refresh both indexes.',
    'Önce Klasörler bölümünden en az bir konum ekleyin.': 'Add at least one search location under Folders first.',
    'Dosyalar okunuyor…': 'Reading files…', 'İçerikler aramaya hazırlanıyor…': 'Preparing content for search…',
    'Hatırladığınız içeriğe yakın dosyalar aranıyor…': 'Finding files with similar meaning…',
    'Önizleme hazırlanıyor…': 'Preparing preview…',
    'Bu aramada sonuç bulunamadı.\nBaşka bir ayrıntıyı anlatarak tekrar deneyin.': 'No results were found.\nTry describing another detail.',
    'Dosya adıyla bulundu; içerik önizlemesini seçerek açın.': 'Found by file name. Select to open the available preview.',
    'Dosya taşınmış veya silinmiş olabilir. Dosya dizinini yenileyin.': 'The file may have moved or been deleted. Refresh the file index.',
    'İşlem durduruluyor; tamamlanınca pencereyi tekrar kapatabilirsiniz.': 'Stopping the current task. Close the window again when it finishes.',
    'Dosya adı / tam kelime araması': 'File name / exact word search',
    'Dosya adı veya tam kelimeyle ara': 'Search a file name or exact words',
    'Dosya adı': 'File name', 'Tam kelime': 'Exact words',
    'Dosya adları / kelimeler aranıyor…': 'Searching file names / exact words…',
    'Aranacak klasörü seçin': 'Choose a folder to search',
    'Arama sorgusu boş olamaz.': 'The search query cannot be empty.',
    'Önce “Anlam dizinini hazırla” düğmesine basın.': 'Prepare the semantic index first from Index status.',
    'Dosya dizini değişmiş veya anlam dizini tamamlanmamış. Anlam dizinini hazırlayın.': 'The file index has changed or preparation is incomplete. Prepare the semantic index.',
    'Model değişmiş. Anlam dizinini yeniden hazırlayın.': 'The model has changed. Prepare the semantic index again.',
    'Yerel model servisine erişilemiyor. Ollama kurulumunu kontrol edin.': 'The local model service is unavailable. Check the Ollama installation.',
    'Projenin yerel model servisi bulunamadı. Ollama kurulumu gerekli.': 'The local model runtime was not found. Install the runtime package.',
    'Qwen3-Embedding-0.6B henüz indirilmemiş. Yerel model kurulumunu tamamlayın.': 'Qwen3-Embedding-0.6B is not available yet. Complete the local model setup.',
    'İçeriği okunabilen dosya yok. Önce dosya dizinini oluşturun.': 'No readable document content is indexed. Create the file index first.',
    'Bu dosyanın metin içeriği dizinde yok. Dosya adıyla aranabilir.': 'This file has no indexed text content. You can find it by file name.',
    'Dosya taşınmış veya silinmiş; son dizinlenen metin gösteriliyor.': 'The file has moved or been deleted. Showing the last indexed text.',
    'Dosya değişmiş olabilir. Metin son dizinlemeden; görsel güncel dosyadandır.': 'The file may have changed. Text is from the last index; the image is from the current file.',
    'Betimlemeyi 6000 karakterden kısa tutun.': 'Keep the description below 6,000 characters.',
    'Dil tercihiniz kaydedildi.': 'Language preference saved.',
    'Anlam dizini hazırlığı durduruldu. Tekrar başlatıldığında kaldığı yerden devam eder.': 'Semantic preparation stopped. It will resume when started again.',
    'Anlam dizini hazırlığı durduruldu. Tekrar başlatabilirsiniz.': 'Semantic preparation stopped. You can start it again.',
    'Anlam dizini hazırlığı durduruldu.': 'Semantic preparation stopped.',
    'Dosya dizini hazırlık sırasında değişti. Anlam dizinini yeniden hazırlayın.': 'The file index changed during preparation. Prepare the semantic index again.',
    'En az bir klasör seçin.': 'Select at least one folder.',
    'Dosya dizinde bulunamadı. Aramayı yenileyin.': 'The file was not found in the index. Run the search again.',
    'Model geçersiz veya uyumsuz vektör döndürdü.': 'The model returned an invalid or incompatible vector.',
    'Model boş vektör döndürdü.': 'The model returned an empty vector.',
}

EN.update({'Aramaya hazırla / güncelle': 'Prepare / update search', 'Tek düğmeyle dosyaları okuyun ve anlam kayıtlarını hazırlayın.': 'Read files and prepare semantic records with one button.', 'Dosyalarınız henüz aramaya hazır değil. Önce seçtiğiniz konumları hazırlayın.': 'Your files are not ready to search. Prepare your selected locations first.', 'Son hazır kayıtlarda arayabilirsiniz. Yeni içerikler için hazırlığı güncelleyin.': 'You can search the last ready records. Update preparation for new content.', 'Bazı konumlar çevrimdışı. Son hazır kayıtlarda arayabilirsiniz.': 'Some locations are offline. You can search the last ready records.', 'Hazırlık sürüyor; tamamlanan kayıtlar korunur.': 'Preparation is running; completed records are preserved.', 'Son hazır kayıtlarda arıyorsunuz. Yeni içerikler için hazırlığı güncelleyin.': 'Searching the last ready records. Update preparation for new content.', 'Güncelleme gerekiyor': 'Update needed', 'Hazırlık sırası: konumları kontrol et → dosyaları oku → anlam kayıtlarını güncelle.': 'Preparation order: check locations → read files → update semantic records.', 'Durdurursanız son hazır dizin korunur. Aynı düğme hazırlığa devam eder.': 'Stopping preserves the last ready index. Use the same button to resume.', 'Disk / ağ yolu ekle': 'Add disk / network path', 'Disk veya ağ konumu': 'Disk or network location', 'Tam klasör yolu veya UNC ağ yolu girin:': 'Enter a full folder path or UNC network path:'})

PATTERNS = [
    (r'([\d.,]+) dosyanın içeriği hazır', '{0} files have indexed content'),
    (r'([\d.,]+) aday', '{0} candidates'),
    (r'([\d.,]+) dosya okundu…', '{0} files read…'),
    (r'Sayfa (\d+) / (\d+)', 'Page {0} / {1}'),
    (r'İçeriğinize en yakın (\d+) aday\. İlgili bölümü önizlemede kontrol edin; benzerlik kesinlik yüzdesi değildir\.', 'Showing the {0} closest candidates. Check the relevant passage; similarity is not a certainty percentage.'),
    (r'([\d.,]+) sonuç bulundu; ilk 200 sonuç gösterilir\.', '{0} results found; showing the first 200.'),
    (r'Aramaya hazır: ([\d.,]+) dosya, ([\d.,]+) metin bölümü\.', 'Ready to search: {0} files, {1} text passages.'),
    (r'([\d.,]+) dosyanın içeriği okundu\. Anlam dizinini hazırlayın\. (\d+) uyarı\.', 'Read content from {0} files. Prepare the semantic index. {1} warnings.'),
    (r'Anlam kayıtları: (\d+)/(\d+) • (.*)', 'Semantic records: {0}/{1} • {2}'),
]
PREFIXES = {
    'Ayarlar okunamadı: ': 'Could not read settings: ',
    'Tercihler kaydedilemedi: ': 'Could not save preferences: ',
    'Ayarlar kaydedilemedi: ': 'Could not save settings: ',
    'Tarama tamamlandı; rapor yazılamadı: ': 'Scanning finished; could not write report: ',
    'Görsel önizleme açılamadı: ': 'Could not open visual preview: ',
    'Yerel model yanıtı: ': 'Local model response: ',
    'Klasör bulunamadı veya bağlantı klasörü: ': 'Folder not found or is a link: ',
}


def translate(text, language='tr'):
    if language != 'en' or not isinstance(text, str):
        return text
    if text in EN:
        return EN[text]
    if text.startswith('Çalışma alanı  /  '):
        return 'Workspace  /  ' + EN.get(text.split('  /  ', 1)[1], text.split('  /  ', 1)[1])
    for pattern, template in PATTERNS:
        match = re.fullmatch(pattern, text, flags=re.DOTALL)
        if match:
            return template.format(*match.groups())
    for prefix, english in PREFIXES.items():
        if text.startswith(prefix):
            return english + translate(text[len(prefix):], language)
    return text


class LocalizedVar(tk.StringVar):
    def __init__(self, master, translator, value=''):
        self.translator = translator
        self.source = str(value)
        super().__init__(master=master, value=translator(self.source))

    def set(self, value):
        self.source = str(value)
        super().set(self.translator(self.source))

    def refresh(self):
        super().set(self.translator(self.source))

# Search Agent vNext — Program ve kullanım rehberi

Yerel dosyaları, dosya adını veya birebir cümleyi bilmeden, hatırlanan içerikle bulmak için Windows masaüstü uygulaması. Bu dosya programın amacı, bileşenleri, kapsamı, kurulumu, çalışma şekli, gereksinimleri ve sınırlarını bir arada açıklar.

## 1. Hızlı başlangıç

1. Windows ZIP paketini bütünüyle yerel bir klasöre çıkarın.
2. SearchAgent.exe dosyasını açın. _internal ve runtime klasörlerini yanında tutun.
3. Klasörler bölümünden aranacak konumları seçin. Yerel klasör seçebilir veya Disk / ağ yolu ekle ile bir tam yol girebilirsiniz.
4. Ana ekrandaki Aramaya hazırla / güncelle düğmesine basın. Dosyaları okuma ve anlam kayıtlarını hazırlama otomatik sırayla çalışır.
5. Hazırlık tamamlandığında dosyadan hatırladığınız bölümü, durumu veya kısa özeti yazın. Ctrl+Enter aramayı başlatır.
6. Sonucu seçerek ilgili metni ve varsa PDF/resim görünümünü inceleyin.

Türkçe / English menüsü dili; Açık / Koyu menüsü temayı değiştirir. Sonuç simgeleri Küçük / Orta / Büyük, görünüm Kartlar / Liste olabilir. Bu tercihler bir sonraki açılışta korunur. Belge metinleri ve dosya adları çevrilmez.

## 2. Arama nasıl çalışır?

Dosyalardan metin çıkarılır; uzun metinler yaklaşık 2200 karakterlik, 250 karakter örtüşen bölümlere ayrılır. Her bölüme dosya adı eklenerek Qwen3-Embedding-0.6B ile 1024 boyutlu bir anlam vektörü üretilir. Sorgu da aynı modele uygun arama yönergesiyle işlenir. Uzun hatırlama notlarının ayrıntıları birlikte değerlendirilir. En yakın 30 dosya, o dosyadaki ilgili bölümle gösterilir.

Bu sürüm sohbet yanıtı üretmez. Kullanılan model bir embedding modelidir. Birbirinden farklı kelimelerle aynı durumu anlatan metinler eşleşebilir. Benzerlik puanı doğruluk yüzdesi değildir; ilgisiz adaylar da çıkabilir. Dosya adıyla arama ve tam kelime araması ayrıca kullanılabilir.

Model ve bölümleme tarifi önceki sürümle korunmuştur. Düşük boyutlu vektör veya daha küçük modele geçilerek kalite azaltılmamıştır.

## 3. Hazırlık ve güncelleme

Dizin yokken ana ekranda hazırlık yönlendirmesi görünür; anlam araması hazırlık yapılana kadar etkinleşmez. Dosya okuma ve model işlemesi arka planda yürütülür. İşlenen kayıt sayısı, aşama ve geçen süre gösterilir. Yeterli örnek oluşursa yaklaşık kalan süre eklenir; bu değer kesin süre değildir.

Sonraki taramada boyutu ve değiştirilme zamanı aynı olan uygun dosyaların metinleri tekrar okunmaz. Veritabanı güvenli bir çalışma kopyası üzerinde güncellenir; değişmeyen belge satırları ve anlam kayıtları yeniden kullanılır. Yeni ve değişen belgelerin metin bölümleri, donanıma göre sınırlı gruplarla modele gönderilir. Varsayılan grup 8 bölümdür.

Hazır dizin güncellenirken önceki tamamlanmış anlam dizini korunur. Durdur işlemi tamamlanan anlam gruplarını saklar; aynı düğme devam eder. İlk dosya taraması durdurulursa önceki dosya dizini korunur; yeniden başlatmada klasör yürüyüşü tekrar yapılır. Dosya okumanın her dosya için kalıcı bir yarım tarama kontrol noktası yoktur.

Önceki dizin varsa güncelleme sırasında arama yapılabilir. Eski kayıtlarda arandığı belirtilir; yeni belgeler hazırlık tamamlanana kadar sonuçlara girmez. Kapsamdan çıkarılan konumların sonuçları filtrelenir. Aynı kullanıcı profilinde ikinci hazırlık işlemi başlatılmaz.

Uygulamanın kendi teslim klasöründeki build, application, releases, reports ve validation çıktıları üst klasörden taramaya dahil edilmez; böylece test belgeleri ve model paketleri sonuçları kirletmez. Kullanıcının başka konumdaki aynı adlı klasörleri bu kuralla dışlanmaz.

Dizin durumu son tarama ve ayarlarla karşılaştırılır. Yeni dosyaları kendiliğinden izleyen Windows servisi bu sürümde yoktur; yeni içerik eklendiğinde güncelleme düğmesini kullanın.

## 4. Çoklu disk ve ağ paylaşımları

Örnek konumlar: C:\Belgeler, D:\Projeler, E:\Arsiv ve \\SUNUCU\Paylasim\Belgeler.

- Birden fazla disk ve paylaşım aynı listede bulunabilir.
- Aynı kök, büyük/küçük harf farkı ve üst/alt klasör çakışmaları birleştirilir.
- Windows tarafından çözülebilen eşlenmiş sürücüler UNC karşılığına dönüştürülür. Eşleme çözülemiyorsa girilen yol korunur.
- USB disk veya paylaşım erişilemiyorsa önceki kayıtlar korunur ve çevrimdışı durum bildirilir. Erişilemeyen alt klasörler de silinmiş gibi kabul edilmez.
- Ulaşılabilir konumdaki gerçekten kaldırılmış dosyalar sonraki taramada dizinden çıkarılır.
- Kullanıcının listeden çıkardığı konumun kayıtları güncellemede kaldırılır.
- Yerel disk seri bilgisi değiştiğinde aynı harfteki farklı diskin dosyaları eski içerikle eşleştirilmeden yeniden okunur.
- Bağlantı geri geldiğinde güncelleme düğmesini yeniden kullanın.
- Ağ gecikmesi, Wi-Fi, VPN, SMB sunucusu ve Windows zaman aşımı hazırlığı yavaşlatabilir. Kilitlenen işletim sistemi ağ çağrısına anlık durdurma garantisi verilmez.

Uygulama Windows oturumunun zaten erişebildiği klasörleri kullanır. Ağ kimlik bilgisi istemez veya saklamaz; farklı oturumların sürücü eşlemeleri farklı olabilir. EXE ve indeksler yerel diskte tutulmalı; ağ paylaşımı belge kaynağı olarak eklenmelidir. Ortak yazılabilir bir SQLite indeksini birden fazla bilgisayarın paylaşması desteklenmez.

Ağ davranışları kesilen/erişimi reddedilen kökler ve eşleme simülasyonlarıyla test edilmiştir. Gerçek NAS/SMB cihazıyla uçtan uca doğrulama bu teslimde yapılmamıştır.

## 5. Desteklenen içerikler ve önizleme

Metin içeriği: PDF (metin katmanı), TXT/CSV, DOCX/DOCM, XLSX/XLS/XLSM/XLSB/ODS, PPTX/PPTM, RTF, ODT/ODP, EPUB, EML, HTML, Markdown, JSON/XML/YAML, günlükler ve yaygın kaynak kodu biçimleri.

OCR açıkken PNG, JPG/JPEG, WEBP, BMP, GIF, TIF/TIFF, TGA ve uygun diğer Pillow resim biçimlerindeki yazılar Tesseract ile okunur. Türkçe ve İngilizce dil verileri pakete dahildir. OCR normal metin okumaktan daha yavaştır. Ayarı değiştirdikten sonra hazırlığı güncelleyin.

PDF ve resimlerin görsel önizlemesi; diğer belgelerin dizinlenmiş metin önizlemesi vardır. Dosya taşınmışsa son dizinlenmiş metin gösterilebilir. Makrolar ve kaynak dosyalar çalıştırılmaz.

Sınırlar: metin katmansız PDF'lerin otomatik toplu OCR'si; eski DOC/PPT; MSG; ses/video konuşmaları; resimdeki nesneleri ve 3D şekilleri anlama; arşiv dosyalarının içini dolaşma bu sürümün anlam araması kapsamına dahil değildir. Desteklenmeyen dosyalar adlarıyla bulunabilir. Büyük içeriklerde 50 MB dosya sınırı, paket belgelerinde 64 MB açılmış içerik sınırı uygulanır. Okuma hatası olan dosyaların yalnızca adı kayıtlı olabilir.

## 6. Minimum ve ortalama önerilen sistem

Aşağıdakiler uygulama için mühendislik önerileridir; bütün bu donanımlarda ayrı ayrı ölçülmüş üretici garantisi değildir.

| Bileşen | Alt başlangıç hedefi | Ortalama öneri |
| --- | --- | --- |
| İşletim sistemi | Windows x64; Windows 10 ayrı doğrulanmadı | Windows 11 x64 |
| İşlemci | 4 çekirdekli güncel x64 CPU | 6–8 çekirdekli Intel Core i5 / AMD Ryzen 5 veya üzeri |
| RAM | 8 GB, küçük koleksiyon ve diğer uygulamalar kapalı | 16 GB; büyük koleksiyon/OCR için 32 GB |
| GPU | İsteğe bağlı; CPU ile çalışabilir | Desteklenen sürücülü NVIDIA GPU, 4 GB+ VRAM |
| Disk | Paket açma ve çalışma için en az 5 GB boş alan, indeks ayrıca | Yerel SSD ve en az 10 GB boş alan; koleksiyona göre artırın |
| Ağ | Paylaşılan klasöre mevcut Windows erişimi | Büyük paylaşımlarda kablolu ağ; indeksler yerel SSD'de |
| Ekran | 1100 × 760 kullanılabilir alan | 1920 × 1080 |

Tam Windows paketi yaklaşık 2 GB açılmış uygulama/model/OCR dosyası içerir; ZIP ve çıkarılan kopya aynı anda tutulacaksa ek alan gerekir. Kaynak sürümünü derlemek için Python 3.12 x64 ve kilitlenmiş geliştirme paketleri gerekir; EXE kullanıcısına ayrıca Python gerekmez.

İndeks alanı dosya sayısından çok metin bölümü sayısına bağlıdır. Bir adet 1024 boyutlu float32 vektörün ham boyutu 4096 bayttır. 100.000 bölümün yalnızca ham vektörleri yaklaşık 391 MiB eder; metinler ve SQLite ek alanı bunun üzerindedir. Güncellemede aktif ve çalışma kopyaları birlikte bulunabileceği için ek boş alan bırakın. Bellekte iki son indeks görünümü tutulabilir; büyük koleksiyonlar daha fazla RAM ister.

Bu sürüm Windows 11, yaklaşık 16 GB RAM ve RTX 4060 8 GB bulunan bilgisayarda doğrulanmıştır. GPU kullanımında modelin yaklaşık 1,14 GiB VRAM ayırdığı gözlendi; bağlam ve işlem grubuna göre değişir. GPU paketindeki CUDA 13 bileşenleri bütün eski NVIDIA kartlarına destek iddiası taşımaz. Uygun sürücü/GPU yoksa CPU yolu kullanılabilir; AMD ROCm paketi dahil değildir, Vulkan desteği cihazına göre değişir. Genel uyumluluk: [Ollama donanım desteği](https://docs.ollama.com/gpu).

## 7. Performans yaklaşımı ve ölçüm

İlk sorguda modelin diskteki ağırlıklardan yüklenmesi, sıcak modelle yapılan aramadan belirgin biçimde uzundur. Uygulama hazır bir indeks açtığında modeli ve anlam vektörlerini arka planda ısıtır. İlk hazırlığın hesaplama maliyeti tamamen ortadan kalkmaz.

Sonraki sorgularda bütün belge metinleri yeniden okunup özet imzaları hesaplanmaz. Dosya/indeks sürümü değişmediğinde anlam vektörleri bellekten kullanılır. Tekrarlanan sorguların vektörleri de sınırlı önbellekte tutulur. Model çalışmazsa anlam araması sessizce kelime aramasına dönmez.

Yerel süre karşılaştırmaları teslim klasörünün reports/performance.json dosyasındadır. Bu dosya belge metni veya sonuç adları içermez. Ölçümler bu bilgisayar ve veri kümesine aittir; her dosya koleksiyonu veya NAS için aynı süre beklenmemelidir.

Gelişmiş değişkenler:
- SEARCH_AGENT_BATCH_SIZE: 1–32, varsayılan 8.
- SEARCH_AGENT_KEEP_ALIVE: modelin boşta tutulması; varsayılan 30m. Daha uzun süre ilk sorgu beklemesini azaltabilir, RAM/VRAM kullanımını sürdürür.
- SEARCH_AGENT_HOME veya --data-dir: özel profil dizini.
- SEARCH_AGENT_RUNTIME: paketlenmiş Ollama/model/OCR klasörü.
- SEARCH_AGENT_OLLAMA_PORT: varsayılan 11434; bağımsız testlerde boş bir yerel port seçilir.

## 8. Yerel veri ve ortak bilgisayar kullanımı

EXE profili varsayılan olarak %LOCALAPPDATA%\SearchAgent-vNext altında tutulur. Windows kullanıcılarının profilleri ayrıdır. Kaynak sürüm kendi proje dizinini kullanır. vNext eski SearchAgent profilinin üzerine yazmaz. tools/migrate_profile.py, açık bir kaynak ve hedef belirtilirse eski ayarları/SQLite indekslerini kopyalayabilir; var olan hedefi ezmez.

İndeks, okunmuş belge metinlerinin yerel kopyasını içerir. Ağdan erişim kaldırılması yerel önbelleği otomatik silmez. Aynı Windows hesabını paylaşan kişiler aynı profil verilerine erişebilir; ayrı Windows hesapları kullanın. Uygulama merkezi kimlik doğrulamalı, çok kullanıcılı bir arama sunucusu değildir.

Ollama servisi yerel loopback adresine bağlanır, uygulamanın başlattığı serviste bulut modu kapatılır. Hazır uyumlu yerel Ollama servisi varsa yeniden kullanılır. Arama için belge metinleri bir bulut LLM servisine gönderilmez.

## 9. Kod ve paket hiyerarşisi

Teslim klasörü:
- source/: GitHub'a hazır kaynak proje, testler, PROGRAM.md, ikonlar ve derleme araçları.
- build/: yerel derleme ara dosyaları.
- application/SearchAgent/: doğrudan çalıştırılabilir EXE, _internal ve runtime.
- releases/: temiz kaynak ZIP'i, tam Windows ZIP'i ve SHA256SUMS.txt.
- reports/: performans ve test sonuçları, yayımlama öncesi değişiklik listesi.
- validation/: özel test profilleri ve arşivden çıkarılan doğrulama kopyaları; paylaşılmaz.

Kaynak projenin temel bileşenleri:
- desktop_app.py, ui_theme.py, i18n.py: arayüz, tema, dil ve görünüm.
- preparation.py: tek adımlı hazırlık, durum ve profil kilidi.
- scope_paths.py: yerel/ağ kökü normalleştirme ve disk kimliği.
- local_catalog.py, catalog_state.py: artımlı dosya dizini ve tutarlılık metaverileri.
- semantic_search.py, model_runtime.py: bölümleme, embedding, önbellek ve sıralama.
- format_readers.py, agents/, services/: belge ve OCR okuyucuları.
- document_preview.py: ilgili bölüm ve PDF/resim önizlemesi.
- tools/: ikon, Windows derleme, paketleme, profil kopyalama ve yerel ölçüm.
- tests/: belge okuma, arama, arayüz, iptal/devam ve ağ/disk hata senaryoları.
- requirements.txt, requirements-dev.txt, requirements-lock.txt: doğrudan, geliştirme ve sınanmış tam bağımlılıklar.

Teknik temel: Python 3.12, CustomTkinter 5.2.2, NumPy, SQLite/FTS5, PyMuPDF, python-docx, openpyxl, python-calamine, python-pptx, Pillow, BeautifulSoup, defusedxml, striprtf, pytesseract, python-dotenv, Ollama ve Tesseract. Tam sürümler requirements-lock.txt ve Windows paketindeki third-party-notices/packages.json içindedir.

## 10. Derleme ve GitHub'a hazırlık

Kaynak proje kökünde Python 3.12 sanal ortamına requirements-lock.txt yüklenir. Testlerin OCR bölümü için İngilizce/Türkçe Tesseract gerekir. tools/build_windows.ps1 ortam/test/ikon/EXE üretimini otomatikleştirir. Manuel derleme SearchAgent.spec üzerinden PyInstaller ile yapılabilir.

Düzenli teslim klasöründe workpath ../build, distpath ../application seçilebilir. tools/package_release.py --project, --application, --output, --runtime ve --tesseract parametreleriyle kaynak ve tam Windows ZIP'lerini oluşturur. Model bloblarının SHA-256 özeti paketleme sırasında doğrulanır. GitHub Actions Windows testleri ve model ağırlıkları içermeyen EXE çıktısı üretir; tam çevrimdışı dağıtım ayrıca hazırlanır.

GitHub'a yalnızca source projesi veya temiz kaynak ZIP'i yüklenir. Büyük Windows ZIP'i kaynak Git deposuna eklenmez; yayımlama kararı verildiğinde Release varlığı olarak sunulur. .env, kişisel konumlar, indeksler, günlükler, sanal ortam ve model ağırlıkları kaynak dışa aktarımına alınmaz. Bu teslim otomatik GitHub yüklemesi/yayını yapmaz.

Üçüncü taraf bileşenlerin lisansları assets/licenses ve third-party-notices altında korunur. Proje sahibinin kendi kaynak lisansı ayrıca seçilir; bu derleme bir kaynak lisansı atamaz. EXE bu geliştirme dağıtımında imzalı değildir.

## 11. Sürüm incelemesi ve doğrulama sınırları

Yayımlama öncesi değişiklik listesi CHANGELOG.md ve teslimin reports klasöründe bulunur. Testler tamamlanmadan yayımlama yapılmaz. Gerçek NAS/SMB, Windows 10 ve düşük RAM'li CPU donanımı için ayrı saha doğrulaması gerekir; yerel hata simülasyonu bu cihazların performans ölçümünün yerine geçmez.

Model bilgisi: [Qwen3-Embedding-0.6B resmî model kartı](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B). Model ailesinin 32K bağlam desteği uygulamanın daha kısa ve kontrollü bölümleme ayarlarını değiştirmez. Bu uygulama 1024 boyut kullanır.

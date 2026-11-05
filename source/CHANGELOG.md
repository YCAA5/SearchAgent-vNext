# vNext — 2026-11-05, yayımlama öncesi

- İlk pencere boyutunun ekran ve ölçeklendirmeye sığacak şekilde seçilmesi.
- Ana ekranda hazırlık/güncelleme kartı; hazır dizin olmadan anlam aramasını yönlendirme.
- Tek düğmeyle dosya okuma ve anlam dizini; aşama, kayıt sayısı, geçen süre ve koşullu kalan süre.
- Uygulamanın kendi derleme/doğrulama/paket çıktılarının üst klasör taramasından dışlanması.
- Değişmeyen belge satırlarının korunması; değişen dosyaların artımlı güncellenmesi.
- İki son anlam indeksinin bellek önbelleği ve sınırlı sorgu vektörü önbelleği.
- Belgeler arası kontrollü embedding grupları; varsayılan 8.
- Hazır anlam dizininin çalışma kopyasıyla korunması; iptal sonrası tamamlanan gruplardan devam.
- Güncellemede önceki hazır kayıtlarda arama ve güncellik bildirimi.
- Çoklu disk/UNC/ağ eşlemesi normalleştirme, yinelenen/çakışan köklerin birleştirilmesi.
- Çevrimdışı kök ve erişilemeyen alt klasörlerde kayıtların korunması; geri bağlanınca güncelleme.
- Disk seri bilgisi değiştiğinde eski içerik önbelleğinin kullanılmaması.
- Kullanıcı profiline ikinci hazırlığı engelleyen kilit; eski sürümden ayrı vNext profili.
- PROGRAM.md içinde kapsam, model, bağımlılıklar, sistem gereksinimleri, kullanım ve sınırlar.
- Kaynak/derleme/uygulama/dağıtım/rapor/doğrulama klasörleriyle ayrı teslim.

Türkçe/İngilizce, iki tema, simge boyutları, kart/liste görünümü ve önizleme korunmuştur.
Qwen modeli ve bölümleme/sıralama tarifi değiştirilmemiştir.

Gerçek ağ cihazı testi yoktur; kesinti/izin/eşleme senaryoları simülasyonlarla doğrulanır.
Tam test ve süre sonuçları teslimin reports klasöründedir. Bu sürüm GitHub'da yayımlanmamıştır.

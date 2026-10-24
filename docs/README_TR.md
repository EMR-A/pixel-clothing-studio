# Pixel Clothing Studio — Türkçe

Bu depo, Pixel Clothing Studio'nun **GPL-3.0-or-later** lisanslı kendi kaynak
kodlarını içerir. Tüm çalışma zinciri tamamen açık kaynak değildir: PyMateria,
kendi kısıtlı lisansıyla kullanıcı tarafından ayrıca kurulan bir bağımlılıktır.
GTA dosyaları, kıyafet görselleri, pixel-skin resource'u, kullanıcı verileri veya
Python/Blender motorları bu kaynak paketinde bulunmaz.

## Kaynaktan çalıştırma

Windows, Tkinter içeren tam Python 3.12 kurulumu ve Edge/Chrome gerekir.
Depo kökünde:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\app.pyw
```

Arayüz motor olmadan açılır; kıyafet üretimi için [BUILD.md](BUILD.md) içindeki
`engine/` düzenini hazırlayın. Denenmiş motor: Blender 5.2.2, Sollumz 2.9.0,
szio 1.3.0.dev9. Oyun dosyaları kullanıcının kendi GTA V Legacy kurulumundan okunur.

## Kullanım

1. Custom kıyafet resource'unu veya `stream` klasörünü seçin. Tek güncelleme için
   değişen `.ydd` modelini ya da `.ytd` dokusunu seçebilirsiniz.
2. Önceki çıktı klasörünü kullanın. Model seçimi ilgili varyantları, doku seçimi
   yalnızca ilgili varyantı üretir; diğer kıyafet kayıtları korunur.
3. Buluta aktar sayfasında **sunucudaki pixel-skin klasörünü** seçin. Bu hedef,
   fotoğrafı alınan kıyafet klasöründen farklıdır.
4. Kendi ImageKit hesabınızın `private_` anahtarını girin. Uygulamadaki rehber,
   hesap ve anahtar adımlarını anlatır. Anahtar kaydedilmez, sunucuya yazılmaz.
5. Yeni/değişen görseller yüklenip doğrulanır; liste ve custom CDN ayarı otomatik
   kurulur. Eski dosyalar çıktıdaki `.pixel-backups/` altında yedeklenir.
6. Açık sunucuda hazır olduğunuzda `restart pixel-skin` çalıştırın. Program sunucuyu
   yeniden başlatmaz. Daha önce yüklenmiş çıktılar anahtar veya tekrar yükleme
   olmadan bağlanabilir.

18 dil ve iki tema desteklenir. Dil değişimi devam eden işlemi veya yolları sıfırlamaz.
Birden fazla paket için aynı çıktı projesini ve ImageKit hesabını kullanın.
Aynı çıktı klasöründe iki programdan eşzamanlı işlem başlatmayın.

## Testler

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\python.exe scripts\check_source.py
```

Testler yapay dosyalar üretir; gerçek oyun dosyası, anahtar, bulut hesabı veya açık
sunucu kullanmaz. İsteğe bağlı 18 dil arayüz testleri ana README'de anlatılmıştır.

## GitHub'a koyarken

Bu temiz kaynak klasörünü kullanın. `.gitignore`; motorları, çıktıları, oyun
dosyalarını, anahtarları, profilleri ve yedekleri dışarıda bırakır.
[Bağımlılık bildirimleri](../THIRD_PARTY_NOTICES.md) ve [LICENSE](../LICENSE)
korunmalıdır. PyMateria'yı eklemeyin. Hazır motorlu ZIP yayımlamadan önce
[RELEASING.md](RELEASING.md) içindeki lisans ve kaynak dağıtımı koşullarını sağlayın.

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
"""Customer-facing instructions shared by the app and exported setup bundle."""
KEYS_URL = 'https://imagekit.io/dashboard/developer/api-keys'
KEY_DOCS_URL = 'https://imagekit.io/docs/api-keys'

KEY_GUIDE = '''1. ImageKit hesabınıza giriş yapın.
“Anahtar sayfasını aç” düğmesi sizi doğrudan ilgili sayfaya götürür. Hesabınız yoksa önce ücretsiz bir hesap oluşturun.

2. Developer Options → API Keys bölümünü açın.
Program için ayrı bir Restricted key oluşturabilirsiniz. Medya erişimini Read and write, hesap yönetimini None seçin. Mevcut bir standart anahtar da kullanılabilir.

3. Private key satırındaki gösterme/göz simgesine basın.
ImageKit isterse hesap şifrenizi kendi sayfasına girin. Google/SSO veya e-posta bağlantısıyla giriş yaptıysanız önce profilinizden bir hesap şifresi belirlemeniz gerekebilir.

4. private_ ile başlayan değeri kopyalayın.
public_ ile başlayan değer bu alana uygun değildir.

5. Bu programa dönüp ImageKit private key alanına yapıştırın.
“Yükle ve otomatik bağla” düğmesine basın. CDN adresini program otomatik bulur.

Anahtar dosyaya kaydedilmez ve skin config'ine yazılmaz. Yalnızca kendi hesabınıza yükleme yapmak için kullanılır; yükleme sonunda alan temizlenir.

Resmi açıklama: https://imagekit.io/docs/api-keys'''

PACKAGE_GUIDE = '''1. Sunucu dosyalarınızda resources klasörünü açın.
Kendi custom kıyafet paketinizin bulunduğu resource'u bulun. Bu klasörün içinde genellikle fxmanifest.lua ve stream klasörü olur.

Örnek:
txData → sunucu.base → resources → [clothes] → benim-kiyafet-paketim

2. “Klasör seç” düğmesinde bu paket klasörünü seçin.
İsterseniz doğrudan paketin stream klasörünü de seçebilirsiniz. Program alt klasörleri tarar; .ydd model ve .ytd doku dosyalarını arar.

3. “Görselleri oluştur” düğmesine basın.
Kıyafetler ve renk/doku seçenekleri sırayla çizilir. Çıktı klasörü varsayılan olarak Belgeler → Pixel Clothing Studio'dur.

Bu sayfada custom kıyafetlerin kaynak klasörünü seçin. pixel-skin hedefi, Buluta aktar sayfasında ayrıca seçilir.

TEK KIYAFET / TEK DOKU GÜNCELLEME
“Tek dosya seç” düğmesiyle değişen .ydd veya .ytd dosyasını seçebilirsiniz. Eşleşen dosyalar aynı resource içinde otomatik bulunur. .ydd seçilirse kıyafetin varyantları, .ytd seçilirse yalnızca o doku üretilir. Önceki üretimin çıktı klasörünü kullanın; diğer kıyafet ve varyant kayıtları korunur. Yeni görüntü içeriği değişmediyse tekrar yüklenmez.

Elinizde ZIP/RAR paket varsa önce çıkarın. Dosyalar kilitli veya okunamıyorsa program bunları raporlar.'''

GAME_GUIDE = '''GTA V yolu çoğu bilgisayarda otomatik bulunur.
Bulunamadıysa “Diğer ayarlar” bölümünde GTA V Legacy oyununun kurulu olduğu klasörü seçin. Bu klasörün içinde GTA5.exe ve x64v.rpf bulunmalıdır.

Örnek:
C:\\Program Files\\Rockstar Games\\Grand Theft Auto V Legacy

Bu yol, kıyafeti karakter iskeletiyle doğru okumak için kullanılır. Oyun dosyaları yüklenmez veya değiştirilmez. FiveM sunucusunun ya da pixel-skin'in klasörü bu alana seçilmez.

Koleksiyon alanını yalnızca program dosya adından cinsiyet ve koleksiyon bulamıyorsa doldurun. Örnek: mp_m_freemode_01_my_pack. Standart ^ işaretli paketlerde alanı boş bırakın.'''

SKIN_GUIDE = '''1. Sunucu dosyalarınızda resources → [charac] → pixel-skin klasörünü bulun.
Buluta aktar sayfasındaki “pixel-skin klasörü” alanından bu klasörü seçin. Seçtiğiniz klasörün içinde fxmanifest.lua, shared ve html bulunmalı. Bu hedef, fotoğrafı çekilecek kıyafet paketinden farklıdır.

2. ImageKit private key’inizi girip “Yükle ve otomatik bağla” düğmesine basın.
Program yalnızca yeni/değişen görselleri yükler, dosyaları doğrular ve otomatik olarak pixel-skin/data/clothing-images.json ile shared/image-sources.lua içindeki CustomCloudBaseUrl ayarını günceller. Görseller yalnızca bulutta kalır; sunucunun başlangıç indirmesine eklenmez. API anahtarınız sunucu dosyalarına yazılmaz.

3. Eski ayarlar, çıktı klasörünüzdeki .pixel-backups altında tarihli bir klasöre yedeklenir. Mevcut kıyafet/varyant eşleştirmeleri birleştirilerek korunur; stok CloudBaseUrl ayarı değiştirilmez.

Görseller zaten yüklüyse aynı çıktı klasörünü seçip “Görseller zaten yüklü → pixel-skin’e bağla” düğmesini kullanın. Anahtar girmeniz veya dosyaları yeniden yüklemeniz gerekmez; önceki doğrulanmış yükleme kayıtları kontrol edilir.

Açık sunucuda değişiklikler için hazır olduğunuzda sunucu konsolunda restart pixel-skin çalıştırın. Program çalışan sunucuyu otomatik yeniden başlatmaz. Sunucu kapalıysa sonraki açılışında yeni ayarları kullanır.

Birden fazla custom paket için aynı çıktı klasörünü ve aynı ImageKit hesabını kullanın. Skin’de farklı bir CDN’e ait korunacak kayıtlar varsa program onları bozmamak için entegrasyonu durdurur. Bu durumda bütün paketlerin bulunduğu çıktı projesini aynı ImageKit hesabına yükleyin.

skin-ayarlari klasörü ayrıca elle kurulum için liste dosyasının ve CDN ayarının kopyasını içerir.'''

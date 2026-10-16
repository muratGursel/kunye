# Değişiklikler

## 0.2.0 — 2026-10-16

Yazıcı eklemek için artık dosya düzenlemek gerekmiyor.

- **Yazıcı Ekle** penceresi: bu bilgisayarda kurulu yazıcılar (CUPS) ve ağda
  kendini duyuran yazıcılar (mDNS) listelenir; listeden seçmek yeterli.
  Etiket yazıcıları üstte, ofis yazıcıları kapalı "Diğer yazıcılar"
  bölümünde.
- **Ağı Tara:** yerel ağda 9100 portunda Zebra yazıcıları bulur; model ve
  çözünürlük yazıcıdan (`~HI`) okunur.
- IP adresiyle elle ekleme; bağlantı denetimi ve Türkçe hata mesajları.
- "Bu bilgisayardaki herkes kullanabilsin" (yönetici parolasıyla
  `/etc/kunye`) ya da yalnızca kullanıcı için kaydetme.
- **Yazıcılar** penceresi (☰ menü): tanımlı yazıcıları listeleme, silme,
  deneme baskısı. Deneme baskısında ad yerine "DENEME BASKISI" yazılır.
- Komut satırı: `kunye yazici-bul`, `yazici-ekle`, `yazici-sil`, `deneme`.
- CUPS yazıcıları tek bir IPP isteğiyle okunur (25 kuyruklu bir sistemde
  27 saniyeden 0,01 saniyeye).
- Bozuk `yazicilar.json` artık uygulamanın açılmasını engellemiyor; hata
  gösteriliyor.
- `tools/sahte_zebra.py`: gerçek yazıcı olmadan deneme için sahte Zebra.

## 0.1.1 — 2026-10-16

- Uygulama kimliği `io.github.muratgursel.Kunye` oldu (önceden
  `com.knicode.Kunye`). 0.1.0'dan yükseltirken eski masaüstü dosyası ve
  simge paketle birlikte kaldırılır; menüdeki Künye kısayolu kendiliğinden
  yenilenir. Panele sabitlenmiş eski kısayol varsa yeniden sabitleyin.

## 0.1.0 — 2026-10-16

İlk sürüm.

- Hazır şablonlar: yetişkin bilekliği, bebek bilekliği, laboratuvar tüpü,
  ilaç/serum etiketi, hasta dosyası etiketi.
- Bitmap tabanlı çizim: Türkçe karakterler her yazıcıda doğru basılır,
  önizleme basılanla aynıdır.
- Code 128 ve QR kod.
- Yazıcılar: Zebra ZPL (TCP 9100 ve CUPS raw), CUPS sürücüsü üzerinden
  görüntü, dosya.
- CSV'den toplu basım (`;`/`,`, UTF-8 / Windows-1254).
- TC kimlik numarası maskeleme, Türkçe büyük harf dönüşümü.
- GTK 4 + libadwaita masaüstü arayüzü: canlı önizleme, basımdan sonra form
  temizleme, eksik alan uyarısı, Ctrl+P ile basım.
- `kunye` komut satırı aracı.
- `/etc/kunye` üzerinden merkezi yazıcı ve şablon dağıtımı.

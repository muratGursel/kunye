# Değişiklikler

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

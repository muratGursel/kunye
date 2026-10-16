# Şablon Rehberi

Künye'deki her etiket türü bir **JSON şablonudur**. Hazır şablonlar
paketle gelir. Hastanenize özel etiketler için yeni şablon yazabilir ya da
hazır olanları değiştirebilirsiniz.

## İçindekiler

1. [Şablonlar nerede?](#1-şablonlar-nerede)
2. [İlk şablon](#2-ilk-şablon)
3. [Şablon alanları](#3-şablon-alanları)
4. [Koordinatlar ve döndürme](#4-koordinatlar-ve-döndürme)
5. [Elemanlar](#5-elemanlar)
6. [Yer tutucular ve süzgeçler](#6-yer-tutucular-ve-süzgeçler)
7. [Barkod boyutları](#7-barkod-boyutları)
8. [Denemek](#8-denemek)

## 1. Şablonlar nerede?

Şablonlar üç yerden, bu sırayla okunur:

| Dizin | Açıklama |
|---|---|
| `/usr/lib/python3/dist-packages/kunye/sablonlar/` | Paketle gelen hazır şablonlar. Değiştirmeyin; güncellemede üzerine yazılır. |
| `/etc/kunye/sablonlar/` | Hastanenin şablonları (bütün kullanıcılar). |
| `~/.config/kunye/sablonlar/` | Kullanıcının kendi şablonları. |

Sonraki dizindeki şablon, **aynı `id`'ye sahip** öncekinin yerine geçer.
Bir hazır şablonu değiştirmek için onu `/etc/kunye/sablonlar/` altına
kopyalayıp düzenleyin; `id`'yi değiştirmezseniz arayüzde hazır şablonun
yerini alır.

```sh
sudo mkdir -p /etc/kunye/sablonlar
sudo cp /usr/lib/python3/dist-packages/kunye/sablonlar/tup-etiketi.json /etc/kunye/sablonlar/
```

## 2. İlk şablon

50 × 30 mm'lik basit bir numune etiketi:

```json
{
  "id": "numune-basit",
  "name": "Basit Numune Etiketi",
  "description": "50 x 30 mm, ad ve numune barkodu",
  "width_mm": 50,
  "height_mm": 30,
  "rotate": 0,
  "fields": [
    {"key": "ad_soyad", "label": "Ad Soyad", "required": true, "example": "Ayşe Çelik"},
    {"key": "numune_no", "label": "Numune No", "required": true, "example": "2610160042"}
  ],
  "elements": [
    {"type": "text", "x_mm": 2, "y_mm": 2, "height_mm": 4, "bold": true,
     "max_width_mm": 46, "text": "{ad_soyad|buyuk}"},
    {"type": "barcode", "x_mm": 3, "y_mm": 9, "height_mm": 12,
     "human_readable": true, "data": "{numune_no}"}
  ]
}
```

Dosyayı `~/.config/kunye/sablonlar/numune-basit.json` olarak kaydedip
`kunye onizle numune-basit --ornek` ile deneyin.

## 3. Şablon alanları

| Alan | Zorunlu | Varsayılan | Açıklama |
|---|---|---|---|
| `id` | evet | | Benzersiz kimlik. Komut satırında kullanılır. Küçük harf ve tire önerilir. |
| `name` | evet | | Arayüzde görünen ad. |
| `description` | | | Arayüzde formun üstünde görünen açıklama. |
| `width_mm`, `height_mm` | evet | | Etiketin **okunduğu yöndeki** genişliği ve yüksekliği (mm). |
| `rotate` | | `0` | Yazıcıya gönderirken saat yönünde döndürme: `0`, `90`, `180`, `270`. |
| `fields` | | | Formdaki alanlar (aşağıda). |
| `elements` | | | Etikete çizilecek öğeler (aşağıda). |

### `fields` — form alanları

| Alan | Zorunlu | Varsayılan | Açıklama |
|---|---|---|---|
| `key` | evet | | Alan anahtarı. Yer tutucularda `{key}` olarak kullanılır ve CSV sütun başlığıyla eşleşir. Küçük harf, rakam ve `_`. |
| `label` | evet | | Formda görünen ad. |
| `required` | | `false` | `true` ise alan boşken basılmaz. |
| `example` | | | `--ornek` ile ve testlerde kullanılan örnek değer. Gerçek hasta bilgisi yazmayın. |

CSV başlıkları şöyle anahtara çevrilir: Türkçe harfler sadeleşir, küçük harfe
çevrilir, boşluk ve işaretler `_` olur. `Doğum Tarihi` → `dogum_tarihi`.

## 4. Koordinatlar ve döndürme

- Bütün ölçüler **milimetre**dir; sol üst köşe `(0, 0)`'dır.
- Koordinatlar etiketin **okunduğu yöne** göre verilir. Bileklikler
  yatay okunur, bu yüzden `width_mm: 279.4, height_mm: 25.4` tanımlanır ve
  yazıcıya `rotate: 90` ile gönderilir.
- Önizleme her zaman okunduğu yönde gösterilir.
- Etiket, yazıcının çözünürlüğünde noktalara çevrilir (203 dpi'da 1 mm ≈ 8
  nokta). Çok ince çizgiler (0,15 mm altı) basılmayabilir.

## 5. Elemanlar

Her elemanın `type` alanı vardır. Her eleman `show_if` alabilir: verilen alan
boşsa eleman hiç çizilmez (ör. alerji girilmediyse alerji kutusu).

### `text` — yazı

| Alan | Varsayılan | Açıklama |
|---|---|---|
| `x_mm`, `y_mm` | | Yazının konumu. `y_mm` yazının üst kenarıdır. |
| `height_mm` | | Yazı boyu (font boyutu, mm). 3 mm yaklaşık 8,5 punto eder. |
| `text` | | Yazı; yer tutucu içerebilir. |
| `bold` | `false` | Kalın yazı. |
| `align` | `left` | `left`, `center`, `right`. `x_mm` buna göre sol kenar, orta ya da sağ kenardır. |
| `max_width_mm` | | Verilirse yazı sığmadığında %60'a kadar küçültülür, yine sığmazsa sonu `…` ile kısaltılır. Hasta adları için mutlaka verin. |

Yazı tipi DejaVu Sans'tır (`fonts-dejavu-core`). Başka bir yazı tipi için
`KUNYE_FONT` ve `KUNYE_FONT_BOLD` ortam değişkenlerine .ttf dosya yolunu verin.

### `barcode` — Code 128 barkod

| Alan | Varsayılan | Açıklama |
|---|---|---|
| `x_mm`, `y_mm` | | Barkodun sol üst köşesi (ilk çubuk). |
| `height_mm` | | Çubuk yüksekliği. |
| `data` | | Barkod verisi; yer tutucu içerebilir. Yalnızca ASCII (Türkçe harf olamaz). |
| `module_mm` | `0.25` | En ince çubuğun genişliği (bkz. [7](#7-barkod-boyutları)). |
| `human_readable` | `false` | Barkodun altına verinin kendisini yazar (2,5 mm). |
| `symbology` | `code128` | Şimdilik yalnızca `code128`. |

Veri boşsa barkod çizilmez. Barkod etiketten taşarsa basım yapılmaz ve hata
gösterilir; taşan barkod okunamaz.

### `qr` — QR kod

| Alan | Varsayılan | Açıklama |
|---|---|---|
| `x_mm`, `y_mm` | | Sol üst köşe. |
| `data` | | Kodlanacak veri (UTF-8). |
| `module_mm` | `0.5` | Bir karenin kenarı. |

Hata düzeltme seviyesi M'dir. Boyut veriye göre büyür; 10 haneli bir protokol
numarası 21 × 21 karedir (0,5 mm ile 10,5 mm). Okuyucuların tanıması için
QR kodun çevresinde en az 4 kare boşluk bırakın.

> **KVKK:** QR kod, herkesin telefonuyla okuyabileceği bir veridir. QR'a ad
> soyad ya da TC kimlik numarası koymayın; protokol numarası yeterlidir.

### `line` — çizgi

`x1_mm`, `y1_mm`, `x2_mm`, `y2_mm`, `thickness_mm` (varsayılan 0,3).

### `box` — kutu

`x_mm`, `y_mm`, `width_mm`, `height_mm`, `thickness_mm` (varsayılan 0,3),
`filled` (varsayılan `false`; `true` ise içi dolu siyah).

## 6. Yer tutucular ve süzgeçler

Yazılarda ve barkod verisinde `{anahtar}` alanın değeriyle değiştirilir.
`|` ile süzgeç eklenebilir, birden çok süzgeç sırayla uygulanır:
`{ad_soyad|buyuk}`.

| Süzgeç | Etki | Örnek |
|---|---|---|
| `buyuk` | Türkçe kurallarıyla büyük harf | `ilknur ışık` → `İLKNUR IŞIK` |
| `kucuk` | Türkçe kurallarıyla küçük harf | `IŞIK` → `ışık` |
| `maskele` | Son 4 karakter dışını `*` yapar | `12345678901` → `*******8901` |

Her şablonda kullanılabilen hazır değerler:

| Yer tutucu | Değer |
|---|---|
| `{bugun}` | Basım günü, `16.10.2026` |
| `{saat}` | Basım saati, `14:35` |

`fields` içinde tanımlanmamış bir anahtar kullanılırsa etiket çizilmez ve
"Şablonda tanımlanmamış alan kullanılmış" hatası verilir.

## 7. Barkod boyutları

Barkod çubukları yazıcının noktalarına tam oturacak şekilde yuvarlanır;
böylece okunabilirlik bozulmaz. `module_mm: 0.25` 203 dpi'da 2 nokta,
300 dpi'da 3 nokta olur.

10 haneli bir rakam dizisi (protokol numarası) Code 128'de 90 modül
genişliğindedir: `module_mm: 0.25` ile **22,5 mm**. Harf içeren veriler
çok daha uzun olur. Barkodun sağında ve solunda okuyucu için en az 10 modül
(0,25 mm ile 2,5 mm) boşluk bırakın.

| Kullanım | Önerilen `module_mm` | `height_mm` |
|---|---|---|
| Bileklik | 0.25 | 10–14 |
| Tüp etiketi | 0.25 | 8–10 |
| Dosya etiketi | 0.25–0.33 | 8–12 |

## 8. Denemek

```sh
kunye alanlar numune-basit                          # alanlar doğru okunuyor mu?
kunye onizle numune-basit --ornek -o deneme.png     # 203 dpi
kunye onizle numune-basit --ornek --dpi 300 -o deneme300.png
kunye onizle numune-basit --ornek --zpl -o deneme.zpl
```

Şablonda hata varsa (eksik alan, bilinmeyen eleman türü, yanlış `rotate`)
komut hatanın hangi dosyada ve hangi elemanda olduğunu yazar. Gerçek yazıcıda
basıp barkodu okutmadan şablonu kullanıma almayın.

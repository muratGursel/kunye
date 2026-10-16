# Yazıcı Kurulumu (Bilgi İşlem)

Künye kurulduktan sonra **hangi yazıcılara basılacağı tanımlanana kadar
basım yapılamaz**. Arayüzde "Yazıcı tanımlı değil" yazar ve Bas düğmesi
soluk görünür. Bu belge yazıcıların nasıl tanımlanacağını anlatır.

## İçindekiler

1. [Hızlı başlangıç](#1-hızlı-başlangıç)
2. [Tanım dosyası nerede?](#2-tanım-dosyası-nerede)
3. [Dosya biçimi](#3-dosya-biçimi)
4. [Yazıcı türleri](#4-yazıcı-türleri)
5. [Çözünürlük (dpi)](#5-çözünürlük-dpi)
6. [Etiket yönü ve kalibrasyon](#6-etiket-yönü-ve-kalibrasyon)
7. [Bütün bilgisayarlara dağıtmak](#7-bütün-bilgisayarlara-dağıtmak)
8. [Sorun giderme](#8-sorun-giderme)

## 1. Hızlı başlangıç

Ağa bağlı bir Zebra bileklik yazıcısı için:

```sh
sudo mkdir -p /etc/kunye
sudo tee /etc/kunye/yazicilar.json >/dev/null <<'EOF'
{
  "acil-zebra": {"kind": "zpl-tcp", "host": "10.10.5.21", "dpi": 203, "description": "Acil triyaj"}
}
EOF
kunye yazicilar        # tanımı kontrol et
kunye bas bileklik-yetiskin -y acil-zebra --ornek   # örnek verilerle deneme baskısı
```

Deneme baskısındaki barkodu bir okuyucuyla okutun: `2026104512` okunmalıdır.
Paketle gelen örnek dosya: `/usr/share/doc/kunye/examples/yazicilar.json`.

## 2. Tanım dosyası nerede?

| Dosya | Kapsam |
|---|---|
| `/etc/kunye/yazicilar.json` | Bilgisayardaki bütün kullanıcılar. Önerilen yer. |
| `~/.config/kunye/yazicilar.json` | Yalnızca o kullanıcı. |

İkisi birlikte okunur. Aynı adlı yazıcı iki dosyada da varsa kullanıcınınki
geçerli olur. Dosya değişikliği Künye yeniden açılınca devreye girer.

## 3. Dosya biçimi

Dosya, yazıcı adından tanımına giden bir JSON nesnesidir. Yazıcı adı
arayüzde ve `kunye bas -y AD` komutunda görünür; boşluksuz ve kısa tutun.

| Alan | Zorunlu | Varsayılan | Açıklama |
|---|---|---|---|
| `kind` | evet | | Yazıcı türü: `zpl-tcp`, `zpl-cups`, `cups-image`, `file` |
| `dpi` | | `203` | Yazıcının çözünürlüğü: 203, 300 ya da 600 |
| `description` | | | Arayüzde adın yanında görünen açıklama |
| `host` | `zpl-tcp` | | Yazıcının IP adresi ya da adı |
| `port` | | `9100` | `zpl-tcp` için TCP portu |
| `queue` | `zpl-cups`, `cups-image` | | CUPS kuyruk adı (`lpstat -e` ile listelenir) |
| `path` | `file` | | Çıktı dosyası (`.zpl` ya da `.png`) |
| `compression` | | `z64` | ZPL görüntü sıkıştırması: `z64` ya da `hex` |

## 4. Yazıcı türleri

### `zpl-tcp` — ağdaki Zebra yazıcı

ZPL komutlarını doğrudan yazıcının 9100 portuna gönderir. CUPS gerekmez.
Yazıcının sabit IP adresi olmalıdır. Erişimi kontrol etmek için:
`nc -zv 10.10.5.21 9100`.

### `zpl-cups` — USB ile bağlı Zebra yazıcı

ZPL'yi bir CUPS kuyruğuna **ham (raw)** olarak gönderir. Kuyruğun sürücüsüz
(raw) kurulması gerekir; Zebra sürücüsüyle kurulmuş bir kuyruk ZPL'yi metin
gibi basar.

```sh
lpinfo -v | grep -i zebra            # yazıcının adresini bul (ör. usb://Zebra/ZD421...)
sudo lpadmin -p Zebra_ZD421 -E -v 'usb://Zebra%20Technologies/ZTC%20ZD421-203dpi?serial=XXXX' -m raw
```

CUPS, raw kuyrukların ileride kaldırılacağı uyarısını verebilir; Pardus 23 ve
25'teki CUPS 2.4 sürümünde çalışmaya devam eder.

### `cups-image` — ZPL bilmeyen yazıcılar

TSC, Godex, Brother gibi yazıcılarda etiket görüntüsü yazıcının **CUPS
sürücüsüyle** basılır. Yazıcıyı önce Pardus'un yazıcı ayarlarından ya da
`http://localhost:631` adresinden üreticinin sürücüsüyle kurun. Künye
etiket boyutunu (`media=Custom.GxYmm`) ve çözünürlüğü (`ppi`) CUPS'a
bildirir; sürücüde de aynı etiket boyutunun seçili olduğundan emin olun.

### `file` — deneme

Yazıcı olmadan denemek içindir. `path` `.png` ile bitiyorsa son etiketin
görüntüsünü yazar; diğer durumlarda ZPL komutlarını dosyanın sonuna ekler.
ZPL çıktısı <https://labelary.com/viewer.html> ile görüntülenebilir
(gerçek hasta bilgisi içeren dosyaları dış sitelere yüklemeyin).

## 5. Çözünürlük (dpi)

`dpi` yazıcının gerçek çözünürlüğüyle aynı olmalıdır; yanlışsa etiket büyük
ya da küçük basılır. Yazıcının üzerindeki etikette ya da model adında yazar
(ör. `ZD421-203dpi`, `ZD621-300dpi`). Bileklik yazıcılarının çoğu 203 ya da
300 dpi'dır.

## 6. Etiket yönü ve kalibrasyon

- Bileklik şablonları yazıcıya **90° döndürülmüş** gönderilir; çünkü
  bileklik yazıcıdan uzun kenarıyla çıkar. Yazı ters çıkıyorsa şablondaki
  `rotate` değerini `270` yapın ([SABLONLAR.md](SABLONLAR.md)).
- Etiketler kayıyor ya da her baskıda boş etiket çıkıyorsa yazıcının
  sensör kalibrasyonunu yapın (Zebra'da çoğunlukla besleme düğmesine
  basılı tutarak). Bu ayar Künye'den yapılmaz.
- Baskı soluksa yazıcının koyuluk (darkness) ayarını artırın.

## 7. Bütün bilgisayarlara dağıtmak

`/etc/kunye/` altındaki dosyalar bütün kullanıcılar için geçerlidir. Bunları
**Lider Ahenk** dosya dağıtımı, Ansible ya da benzeri bir araçla bütün
istemcilere gönderebilirsiniz:

```text
/etc/kunye/yazicilar.json          yazıcı tanımları
/etc/kunye/sablonlar/*.json        hastaneye özel şablonlar
```

Servislere göre farklı yazıcı gerekiyorsa her servisin bilgisayarlarına o
servisin `yazicilar.json` dosyasını gönderin. Kullanıcılar listeden yalnızca
kendi yazıcılarını görür.

## 8. Sorun giderme

| Belirti | Olası neden ve çözüm |
|---|---|
| Arayüzde "Yazıcı tanımlı değil" | `yazicilar.json` yok ya da okunamıyor. `kunye yazicilar` komutunun çıktısına bakın. |
| `JSON okunamadı` | Dosyada virgül, tırnak ya da parantez hatası var. `python3 -m json.tool /etc/kunye/yazicilar.json` hatanın yerini gösterir. |
| `… yazıcısına bağlanılamadı` | IP adresi yanlış, yazıcı kapalı ya da 9100 portu güvenlik duvarında kapalı. |
| `'lp' komutu bulunamadı` | `sudo apt install cups-client` |
| `CUPS hatası: … does not exist` | `queue` adı yanlış. Doğru ad için `lpstat -e`. |
| Etikette anlamsız yazılar/kodlar çıkıyor | `zpl-cups` kuyruğu raw değil, sürücüyle kurulmuş. Kuyruğu `-m raw` ile yeniden kurun. |
| Hiçbir şey basılmıyor, hata da yok (eski Zebra) | Eski firmware Z64 sıkıştırmasını desteklemiyor olabilir: `"compression": "hex"` ekleyin. |
| Etiket büyük/küçük basılıyor | `dpi` yanlış. |
| Barkod okunmuyor | Koyuluğu artırın; okuyucunun Code 128'i okuyacak şekilde ayarlı olduğunu kontrol edin. |

# Geliştirici Notları

## Kaynaktan çalıştırmak

```sh
sudo apt install python3-pil python3-qrcode python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 fonts-dejavu-core
git clone https://github.com/muratGursel/kunye.git && cd kunye
python3 -m kunye sablonlar        # komut satırı
python3 -m kunye arayuz           # masaüstü arayüzü
```

## Yapı

```text
kunye/
  model.py      Şablon veri modeli ve JSON doğrulama
  catalog.py    Hazır, /etc ve kullanıcı şablonlarını bulma
  fill.py       {alan|süzgeç} yer tutucuları, Türkçe büyük/küçük harf, maskeleme
  code128.py    Bağımlılıksız Code 128 kodlayıcı
  render.py     Şablonu yazıcı çözünürlüğünde 1 bitlik görüntüye çizme
  zpl.py        Görüntüyü ZPL ^GF komutuna çevirme (Z64 / hex)
  printers.py   Yazıcı tanımları; TCP 9100, CUPS raw, CUPS görüntü, dosya
  data.py       CSV okuma (ayraç ve kodlama tanıma, başlık eşleştirme)
  config.py     /etc/kunye ve ~/.config/kunye dizinleri
  cli.py        Komut satırı
  gui/          GTK 4 + libadwaita arayüzü
    app.py      Uygulama, eylemler, kısayollar
    window.py   Ana pencere
    compat.py   Pardus 23 (GTK 4.8, libadwaita 1.2) uyumluluğu
  sablonlar/    Hazır şablonlar
packaging/      .deb paketleme
tools/          Geliştirme araçları (arayüz ekran görüntüsü)
```

## Tasarım kararları

**Her şey bitmap.** Etiket Pillow ile yazıcının çözünürlüğünde 1 bitlik
görüntüye çizilir ve ZPL'nin `^GF` grafik alanıyla gönderilir. Zebra'nın
yerleşik yazı tiplerini ve barkod komutlarını kullanmamanın nedenleri:

- Yerleşik fontlarda Türkçe harfler (ş, ğ, ı, İ) çoğu yazıcıda yok ya da
  `^CI28` ve font yüklemesi gerektiriyor.
- Önizleme basılanla birebir aynı olur.
- Aynı görüntü ZPL bilmeyen yazıcılara CUPS üzerinden gönderilebilir.

Bedeli veri boyutudur: 25 × 279 mm bir bileklik 203 dpi'da ~58 KB ham
veridir; Z64 (zlib + base64) ile birkaç KB'a iner.

**Barkodlar tam noktaya oturur.** Modül genişliği tam sayı noktaya
yuvarlanır; ölçekleme yapılmaz.

**Hasta güvenliği arayüzde.** Basımdan sonra form temizlenir; önizleme hata
verdiğinde eski görüntü silinir (aksi halde başka hastanın etiketi ekranda
kalabilir); toplu basımda önce bütün etiketler çizilir, hata varsa hiçbiri
gönderilmez.

**Uyumluluk.** Hedef Pardus 23 (Python 3.11, Pillow 9.4, GTK 4.8,
libadwaita 1.2) ve Pardus 25. Yeni API'ler (`Gtk.FileDialog`,
`Adw.AlertDialog`, `Adw.AboutDialog`) yalnızca varsa kullanılır;
`gui/compat.py`.

## Testler

```sh
sudo apt install python3-pytest libzbar0
pip install --user pyzbar     # ya da: sudo apt install python3-pyzbar (varsa)
python3 -m pytest
```

`tests/test_render.py` her hazır şablonu 203 ve 300 dpi'da çizer ve
barkodları **zbar ile gerçekten okutur**. Yeni şablon eklediğinizde otomatik
olarak bu teste girer.

### Arayüz ekran görüntüleri

`tools/gui_snapshot.py` arayüzü bir senaryo üzerinden sürer (doldurma, basma,
eksik alan, hatalı barkod, toplu basım) ve her adımda PNG kaydeder. Ekransız
çalıştırmak için GTK'nın Broadway arka ucu kullanılır; **Broadway yalnızca bir
tarayıcı bağlıyken çizim yapar**:

```sh
gtk4-broadwayd :7 &                       # http://localhost:8087 adresini bir tarayıcıda açın
mkdir -p /tmp/kunye-cfg/kunye
echo '{"deneme": {"kind": "file", "path": "/tmp/kunye-shots/basilan.zpl"}}' > /tmp/kunye-cfg/kunye/yazicilar.json
XDG_CONFIG_HOME=/tmp/kunye-cfg GDK_BACKEND=broadway BROADWAY_DISPLAY=:7 \
    python3 tools/gui_snapshot.py /tmp/kunye-shots
```

## Paket ve sürüm

```sh
sh packaging/build-deb.sh          # dist/kunye_SÜRÜM_all.deb
sudo apt install ./dist/kunye_*_all.deb
```

Paket yalnızca `dpkg-deb` ile, debhelper olmadan üretilir. Sürüm numarası
`kunye/__init__.py` içindeki `__version__`'dan okunur.

Yeni sürüm çıkarmak için:

1. `kunye/__init__.py` içinde `__version__`'ı artırın, `CHANGELOG.md`'ye
   ekleyin.
2. `git tag v0.2.0 && git push --tags`
3. GitHub Actions testleri çalıştırır, paketi üretir, temiz bir sistemde
   kurup dener ve `.deb`'i sürüm sayfasına yükler.

## Katkı

- Kullanıcıya görünen bütün metinler Türkçedir.
- Yeni özellik için test ekleyin; barkod ya da çizimle ilgiliyse zbar ile
  okutan bir test olsun.
- Örnek verilerde gerçek hasta bilgisi kullanmayın.

#!/bin/sh
# Paketi hiçbir şey kurulu olmayan bir Debian konteynerinde kurar ve dener.
#   sh packaging/temiz-kurulum-testi.sh dist/kunye_0.1.0_all.deb debian:12   # Pardus 23 tabanı
#   sh packaging/temiz-kurulum-testi.sh dist/kunye_0.1.0_all.deb debian:13   # Pardus 25 tabanı
# Docker gerekir.
set -eu

DEB=$(realpath "$1")
IMAGE=${2:-debian:13}
ROOT=$(cd "$(dirname "$0")/.." && pwd)

docker run --rm -i \
    -v "$DEB:/tmp/$(basename "$DEB"):ro" \
    -v "$ROOT/tools:/tmp/tools:ro" \
    -e DEB="/tmp/$(basename "$DEB")" \
    "$IMAGE" sh -eu <<'EOF'
export DEBIAN_FRONTEND=noninteractive
. /etc/os-release
echo "== $PRETTY_NAME"
apt-get update -qq
echo "== kurulum (apt, öntanımlı ayarlarla)"
apt-get install -y -qq "$DEB" >/tmp/apt.log 2>&1 || { tail -30 /tmp/apt.log; exit 1; }
dpkg -s kunye | sed -n 's/^\(Status\|Version\): /  \1: /p'

echo "== komut satırı"
kunye --version
kunye sablonlar
kunye yazicilar
for t in bileklik-yetiskin bileklik-bebek tup-etiketi ilac-etiketi dosya-etiketi; do
    kunye onizle "$t" --ornek -o "/tmp/$t.png" >/dev/null
done
echo "  5 şablon çizildi"

echo "== hata mesajları (Python hata dökümü olmamalı)"
kunye bas bileklik-yetiskin -y yok 2>&1 | tee /tmp/err.txt || true
kunye onizle yok 2>&1 | tee -a /tmp/err.txt || true
! grep -q Traceback /tmp/err.txt

echo "== masaüstü dosyaları"
test -f /usr/share/applications/io.github.muratgursel.Kunye.desktop
test -f /usr/share/icons/hicolor/scalable/apps/io.github.muratgursel.Kunye.svg
test -f /usr/share/doc/kunye/examples/yazicilar.json
echo "  tamam"

echo "== arayüz (Broadway, ekransız)"
apt-get install -y -qq libgtk-4-bin >/dev/null 2>&1   # yalnızca test için: gtk4-broadwayd
gtk4-broadwayd :9 >/dev/null 2>&1 &
sleep 1
mkdir -p /tmp/cfg/kunye /tmp/shots
echo '{"deneme": {"kind": "file", "path": "/tmp/shots/basilan.zpl"}}' > /tmp/cfg/kunye/yazicilar.json
# Yazıcısız açılış: temiz sistemde kullanıcının ilk göreceği durum
GDK_BACKEND=broadway BROADWAY_DISPLAY=:9 timeout 5 kunye-arayuz >/tmp/gui0.log 2>&1 || test $? -eq 124
! grep -q Traceback /tmp/gui0.log
echo "  yazıcısız açılış: hata yok"
# Senaryo: doldurma, basma, eksik alan, hatalı barkod, toplu basım
cd /tmp
XDG_CONFIG_HOME=/tmp/cfg GDK_BACKEND=broadway BROADWAY_DISPLAY=:9 \
    timeout 60 python3 tools/gui_snapshot.py /tmp/shots >/tmp/gui.log 2>&1 || true
grep -E "temiz|önizleme" /tmp/gui.log | sed 's/^/  /'
if grep -q Traceback /tmp/gui.log; then cat /tmp/gui.log; exit 1; fi
echo "  basılan etiket: $(grep -c '^\^XA' /tmp/shots/basilan.zpl)"

echo "== yazıcı ekleme (sahte Zebra, komut satırı)"
python3 /tmp/tools/sahte_zebra.py --host 127.0.0.1 --port 19100 --model ZD421-300dpi \
    --cikti /tmp/zebra.zpl >/tmp/zebra.log 2>&1 &
sleep 1
kunye yazici-bul 2>&1 | sed 's/^/  /'
kunye yazici-ekle acil --ag 127.0.0.1:19100 --aciklama "Acil triyaj" --sistem | sed 's/^/  /'
kunye yazicilar | grep -q "acil .*zpl-tcp .*300 dpi"
kunye deneme acil bileklik-yetiskin | sed 's/^/  /'
sleep 1
test "$(grep -c '^\^XA' /tmp/zebra.zpl)" -eq 1
echo "  sahte Zebra'ya ulaşan deneme etiketi: 1"
kunye yazici-sil acil --sistem | sed 's/^/  /'

echo "== yazıcı ekleme (arayüz)"
rm -rf /tmp/cfg /etc/kunye && mkdir -p /tmp/cfg /tmp/yshots
XDG_CONFIG_HOME=/tmp/cfg KUNYE_SENARYO=yazici KUNYE_TARAMA_PORT=19100 GDK_BACKEND=broadway \
    BROADWAY_DISPLAY=:9 timeout 90 python3 tools/gui_snapshot.py /tmp/yshots >/tmp/ygui.log 2>&1 || true
grep -E "bulunan|taramada|eklenen|hatalı adres" /tmp/ygui.log | sed 's/^/  /'
if grep -q Traceback /tmp/ygui.log; then cat /tmp/ygui.log; exit 1; fi
grep -q "eklenen: zd421 zpl-tcp 300 dpi /etc/kunye/yazicilar.json" /tmp/ygui.log
test "$(grep -c '^\^XA' /tmp/zebra.zpl)" -eq 2
echo "  arayüzden eklenen yazıcıya deneme etiketi ulaştı"

echo "== kaldırma"
apt-get remove -y -qq kunye >/dev/null 2>&1
test ! -e /usr/lib/python3/dist-packages/kunye
echo "  temiz kaldırıldı"
echo "== BAŞARILI: $PRETTY_NAME"
EOF

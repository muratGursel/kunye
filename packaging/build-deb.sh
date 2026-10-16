#!/bin/sh
# Pardus/Debian için kunye .deb paketini üretir: dist/kunye_SÜRÜM_all.deb
# Yalnızca dpkg-deb gerekir (Pardus'ta öntanımlı kurulu). Kullanım: sh packaging/build-deb.sh
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/kunye/__init__.py")
if [ -z "$VERSION" ]; then
    echo "Sürüm kunye/__init__.py dosyasından okunamadı" >&2
    exit 1
fi

BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT
PKG="$BUILD/kunye"
LIB="$PKG/usr/lib/python3/dist-packages/kunye"
DOC="$PKG/usr/share/doc/kunye"

install -d "$PKG/DEBIAN" "$PKG/usr/bin" "$LIB/gui" "$LIB/sablonlar" "$DOC/examples" \
    "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/scalable/apps"

install -m 644 "$ROOT"/kunye/*.py "$LIB/"
install -m 644 "$ROOT"/kunye/gui/*.py "$LIB/gui/"
install -m 644 "$ROOT"/kunye/sablonlar/*.json "$LIB/sablonlar/"
install -m 755 "$ROOT/packaging/debian/kunye" "$PKG/usr/bin/kunye"
install -m 755 "$ROOT/packaging/debian/kunye-arayuz" "$PKG/usr/bin/kunye-arayuz"
install -m 644 "$ROOT/packaging/debian/io.github.muratgursel.Kunye.desktop" "$PKG/usr/share/applications/"
install -m 644 "$ROOT/packaging/debian/io.github.muratgursel.Kunye.svg" \
    "$PKG/usr/share/icons/hicolor/scalable/apps/"
install -m 644 "$ROOT/README.md" "$ROOT/CHANGELOG.md" "$ROOT"/docs/*.md "$DOC/"
install -m 644 "$ROOT/packaging/debian/yazicilar.json.ornek" "$DOC/examples/yazicilar.json"
install -m 644 "$ROOT/packaging/debian/copyright" "$DOC/copyright"
install -m 755 "$ROOT/packaging/debian/postinst" "$ROOT/packaging/debian/prerm" "$PKG/DEBIAN/"

SIZE=$(du -sk "$PKG/usr" | cut -f1)
sed -e "s/@VERSION@/$VERSION/" -e "s/@SIZE@/$SIZE/" \
    "$ROOT/packaging/debian/control" > "$PKG/DEBIAN/control"
(cd "$PKG" && find usr -type f -exec md5sum {} + > DEBIAN/md5sums)

mkdir -p "$ROOT/dist"
OUT="$ROOT/dist/kunye_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$PKG" "$OUT" >/dev/null
echo "$OUT"

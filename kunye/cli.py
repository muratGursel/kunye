"""Künye komut satırı arayüzü."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .catalog import all_templates, find_template
from .data import read_csv
from .model import Template, TemplateError
from .printers import PrinterError, load_printers
from .render import RenderError, for_print, render
from .zpl import to_zpl


class UsageError(Exception):
    pass


def _parse_pairs(pairs: list[str]) -> dict[str, str]:
    values = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise UsageError(f"Alan 'anahtar=değer' biçiminde olmalı: {pair}")
        values[key.strip()] = value
    return values


def _records(args, template: Template) -> list[dict[str, str]]:
    base = template.example_values() if args.ornek else {}
    base.update(_parse_pairs(args.alan))
    if args.csv:
        rows = read_csv(Path(args.csv))
        if not rows:
            raise UsageError(f"{args.csv}: kayıt bulunamadı.")
        records = [{**base, **row} for row in rows]
    else:
        records = [base]
    for n, rec in enumerate(records, start=1):
        missing = template.missing_fields(rec)
        if missing:
            names = ", ".join(f"{f.label} ({f.key})" for f in missing)
            where = f"{n}. kayıt: " if args.csv else ""
            raise UsageError(f"{where}Zorunlu alan(lar) eksik: {names}")
    return records


def cmd_sablonlar(args) -> None:
    for tpl in all_templates().values():
        print(f"{tpl.id:<22} {tpl.name}  ({tpl.width_mm:g} x {tpl.height_mm:g} mm)")


def cmd_alanlar(args) -> None:
    tpl = find_template(args.sablon)
    print(f"{tpl.name}\n{tpl.description}\n")
    for f in tpl.fields:
        mark = "*" if f.required else " "
        print(f" {mark} {f.key:<16} {f.label:<20} örnek: {f.example}")
    print("\n* zorunlu alan")


def cmd_yazicilar(args) -> None:
    printers = load_printers()
    if not printers:
        print("Tanımlı yazıcı yok. Arayüzde ☰ → Yazıcılar'dan ya da şu komutlarla ekleyin:\n"
              "  kunye yazici-bul            (kurulu ve ağdaki yazıcıları listeler)\n"
              "  sudo kunye yazici-ekle AD --ag IP --sistem\n"
              "Ayrıntılar: /usr/share/doc/kunye/YAZICILAR.md")
    for p in printers.values():
        target = p.host or p.queue or p.path
        print(f"{p.name:<18} {p.kind:<11} {p.dpi} dpi  {target}  {p.description}")


def cmd_yazici_bul(args) -> None:
    from . import discovery

    found = discovery.cups_printers() + discovery.mdns_printers()
    if args.tara:
        print("Ağ taranıyor (9100 portu)…", file=sys.stderr)
        known = {(f.host, f.port) for f in found}
        found += [f for f in discovery.scan_network() if (f.host, f.port) not in known]
    others = [f for f in found if not f.label]
    if not args.hepsi:
        found = [f for f in found if f.label]
    if not found:
        print("Etiket yazıcısı bulunamadı. Ağdaki Zebra yazıcıları aramak için: kunye yazici-bul --tara")
    configured = {(p.host, p.queue) for p in load_printers().values()}
    for f in sorted(found, key=lambda f: not f.label):
        print(f"{f.title}\n    {f.subtitle}")
        if (f.host, f.queue) in configured:
            print("    (zaten tanımlı)")
            continue
        target = f"--cups {f.queue}" if f.source == "cups" else f"--ag {f.host}" + (
            f":{f.port}" if f.port != discovery.ZPL_PORT else "")
        print(f"    eklemek için: sudo kunye yazici-ekle {f.suggested_name()} {target} --sistem")
    if others and not args.hepsi:
        print(f"\n(Ayrıca {len(others)} ofis yazıcısı var; listelemek için: kunye yazici-bul --hepsi)")


def cmd_yazici_ekle(args) -> None:
    from . import discovery
    from .printers import printers_path, updated_printers_json, write_printers_file

    if args.ag:
        try:
            found = discovery.manual_network_printer(args.ag)
        except ValueError as e:
            raise UsageError(str(e)) from None
        if not found.zebra:
            print("Uyarı: yazıcı Zebra olarak tanınmadı; ZPL desteklemiyorsa etiket basılamaz.",
                  file=sys.stderr)
    else:
        queues = {f.queue: f for f in discovery.cups_printers()}
        if args.cups not in queues:
            known = ", ".join(sorted(queues)) or "(yok)"
            raise UsageError(f"'{args.cups}' adlı CUPS yazıcısı yok. Kurulu yazıcılar: {known}")
        found = queues[args.cups]
    dpi = args.dpi or found.dpi
    if not dpi:
        dpi = 203
        print("Uyarı: çözünürlük anlaşılamadı, 203 dpi varsayıldı. Farklıysa --dpi verin.", file=sys.stderr)
    zpl = True if args.zpl else False if args.goruntu else None
    printer = discovery.to_printer(found, args.ad, dpi, args.aciklama, zpl)
    path = printers_path(args.sistem)
    write_printers_file(path, updated_printers_json(path, add=printer))
    print(f"'{printer.name}' eklendi ({printer.kind}, {printer.dpi} dpi): {path}")
    print(f"Deneme baskısı için: kunye deneme {printer.name}")


def cmd_yazici_sil(args) -> None:
    from .printers import printers_path, read_printers_file, updated_printers_json, write_printers_file

    path = printers_path(args.sistem)
    if args.ad not in read_printers_file(path):
        raise UsageError(f"'{args.ad}' {path} içinde tanımlı değil.")
    write_printers_file(path, updated_printers_json(path, remove=args.ad))
    print(f"'{args.ad}' silindi: {path}")


def cmd_deneme(args) -> None:
    printers = load_printers()
    if args.yazici not in printers:
        known = ", ".join(sorted(printers)) or "(yok)"
        raise UsageError(f"'{args.yazici}' adlı yazıcı tanımlı değil. Tanımlı yazıcılar: {known}")
    printer = printers[args.yazici]
    tpl = find_template(args.sablon)
    printer.send(for_print(render(tpl, tpl.test_values(), printer.dpi), tpl.rotate))
    print(f"Deneme etiketi ({tpl.name}) {printer.name} yazıcısına gönderildi. "
          "Barkodu okutarak kontrol edin.")


def cmd_onizle(args) -> None:
    tpl = find_template(args.sablon)
    records = _records(args, tpl)
    out = Path(args.cikti)
    for n, rec in enumerate(records, start=1):
        image = render(tpl, rec, args.dpi)
        if args.zpl:
            text = to_zpl(for_print(image, tpl.rotate), args.adet)
            path = out if len(records) == 1 else out.with_stem(f"{out.stem}-{n}")
            path.write_text(text, encoding="ascii")
        else:
            path = out if len(records) == 1 else out.with_stem(f"{out.stem}-{n}")
            image.save(path, dpi=(args.dpi, args.dpi))
        print(f"Yazıldı: {path}")


def cmd_bas(args) -> None:
    tpl = find_template(args.sablon)
    printers = load_printers()
    if args.yazici not in printers:
        known = ", ".join(sorted(printers)) or "(yok)"
        raise UsageError(f"'{args.yazici}' adlı yazıcı tanımlı değil. Tanımlı yazıcılar: {known}")
    printer = printers[args.yazici]
    records = _records(args, tpl)
    # Önce hepsini çiz: veri hatası yarım kalmış bir toplu basıma yol açmasın
    images = [for_print(render(tpl, rec, printer.dpi), tpl.rotate) for rec in records]
    for image in images:
        printer.send(image, args.adet)
    print(f"{len(images)} etiket {printer.name} yazıcısına gönderildi ({args.adet} kopya).")


def cmd_arayuz(args) -> None:
    try:
        from .gui.app import main as gui_main
    except (ImportError, ValueError) as e:
        raise UsageError(f"Grafik arayüz için GTK 4 ve libadwaita gerekli "
                         f"(python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1): {e}") from None
    raise SystemExit(gui_main())


def _add_data_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("sablon", help="şablon kimliği ya da .json dosyası")
    p.add_argument("-a", "--alan", action="append", default=[], metavar="ANAHTAR=DEĞER",
                   help="alan değeri (birden çok kez verilebilir)")
    p.add_argument("--csv", help="toplu basım için CSV dosyası (her satır bir etiket)")
    p.add_argument("--ornek", action="store_true", help="şablondaki örnek değerleri kullan")
    p.add_argument("-n", "--adet", type=int, default=1, help="her etiketten kopya sayısı")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kunye", description="Künye — hasta bilekliği, barkod ve etiket basıcı")
    parser.add_argument("--surum", "--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="komut", required=True)

    sub.add_parser("sablonlar", help="mevcut şablonları listele").set_defaults(func=cmd_sablonlar)

    p = sub.add_parser("alanlar", help="bir şablonun alanlarını göster")
    p.add_argument("sablon")
    p.set_defaults(func=cmd_alanlar)

    sub.add_parser("yazicilar", help="tanımlı yazıcıları listele").set_defaults(func=cmd_yazicilar)

    p = sub.add_parser("yazici-bul", help="bu bilgisayardaki ve ağdaki yazıcıları bul")
    p.add_argument("--tara", action="store_true", help="yerel ağda Zebra yazıcı ara (9100 portu)")
    p.add_argument("--hepsi", action="store_true", help="ofis yazıcılarını da listele")
    p.set_defaults(func=cmd_yazici_bul)

    p = sub.add_parser("yazici-ekle", help="yazıcı tanımla")
    p.add_argument("ad", help="yazıcının Künye'deki adı (ör. acil-zebra)")
    where = p.add_mutually_exclusive_group(required=True)
    where.add_argument("--ag", metavar="IP[:PORT]", help="ağdaki Zebra yazıcının adresi")
    where.add_argument("--cups", metavar="KUYRUK", help="bu bilgisayarda kurulu yazıcı (lpstat -e)")
    lang = p.add_mutually_exclusive_group()
    lang.add_argument("--zpl", action="store_true", help="CUPS yazıcısı Zebra (ZPL) dilini anlıyor")
    lang.add_argument("--goruntu", action="store_true", help="CUPS yazıcısına sürücüsüyle görüntü gönder")
    p.add_argument("--dpi", type=int, choices=(203, 300, 600), help="çözünürlük (bulunamazsa 203)")
    p.add_argument("--aciklama", default="", help="arayüzde görünecek açıklama")
    p.add_argument("--sistem", action="store_true", help="bu bilgisayardaki herkes için (/etc/kunye, sudo gerekir)")
    p.set_defaults(func=cmd_yazici_ekle)

    p = sub.add_parser("yazici-sil", help="yazıcı tanımını sil")
    p.add_argument("ad")
    p.add_argument("--sistem", action="store_true", help="/etc/kunye içindeki tanımı sil (sudo gerekir)")
    p.set_defaults(func=cmd_yazici_sil)

    p = sub.add_parser("deneme", help="yazıcıya deneme etiketi bas")
    p.add_argument("yazici", help="yazıcı adı")
    p.add_argument("sablon", nargs="?", default="dosya-etiketi", help="şablon (öntanımlı: dosya-etiketi)")
    p.set_defaults(func=cmd_deneme)

    p = sub.add_parser("onizle", help="etiketi PNG (ya da ZPL) dosyasına yaz")
    _add_data_args(p)
    p.add_argument("-o", "--cikti", default="onizleme.png", help="çıktı dosyası")
    p.add_argument("--dpi", type=int, default=203, help="çözünürlük (203, 300, 600)")
    p.add_argument("--zpl", action="store_true", help="PNG yerine ZPL çıktısı üret")
    p.set_defaults(func=cmd_onizle)

    sub.add_parser("arayuz", help="grafik arayüzü aç").set_defaults(func=cmd_arayuz)

    p = sub.add_parser("bas", help="etiketi yazıcıya gönder")
    _add_data_args(p)
    p.add_argument("-y", "--yazici", required=True, help="yazicilar.json içindeki yazıcı adı")
    p.set_defaults(func=cmd_bas)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (UsageError, TemplateError, RenderError, PrinterError, OSError) as e:
        print(f"kunye: hata: {e}", file=sys.stderr)
        return 1
    return 0

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
        print("Tanımlı yazıcı yok. /etc/kunye/yazicilar.json ya da ~/.config/kunye/yazicilar.json "
              "dosyasını oluşturun.\nÖrnek: /usr/share/doc/kunye/examples/yazicilar.json — "
              "ayrıntılar: /usr/share/doc/kunye/YAZICILAR.md")
    for p in printers.values():
        target = p.host or p.queue or p.path
        print(f"{p.name:<18} {p.kind:<11} {p.dpi} dpi  {target}  {p.description}")


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

"""Yazıcı tanımları ve etiketi yazıcıya gönderme.

yazicilar.json örneği::

    {
      "acil-zebra": {"kind": "zpl-tcp", "host": "10.10.5.21", "dpi": 203},
      "lab-zebra":  {"kind": "zpl-cups", "queue": "Zebra_ZD421", "dpi": 300},
      "servis-tsc": {"kind": "cups-image", "queue": "TSC_TE210", "dpi": 203}
    }
"""

from __future__ import annotations

import io
import json
import os
import socket
import subprocess
import tempfile
from dataclasses import dataclass, field, fields
from pathlib import Path

from PIL import Image

from .config import config_dirs
from .zpl import to_zpl

KINDS = ("zpl-tcp", "zpl-cups", "cups-image", "file")


class PrinterError(RuntimeError):
    pass


@dataclass
class Printer:
    name: str
    kind: str
    dpi: int = 203
    host: str | None = None
    port: int = 9100
    queue: str | None = None
    path: str | None = None
    compression: str = "z64"
    description: str = ""
    source: Path | None = field(default=None, compare=False, repr=False)  # tanımın okunduğu dosya

    def send(self, image: Image.Image, copies: int = 1) -> None:
        """``image`` yazıcı yönünde (döndürülmüş) olmalıdır."""
        if self.kind == "zpl-tcp":
            self._send_tcp(to_zpl(image, copies, self.compression).encode("ascii"))
        elif self.kind == "zpl-cups":
            self._lp(["-o", "raw"], to_zpl(image, copies, self.compression).encode("ascii"))
        elif self.kind == "cups-image":
            self._send_cups_image(image, copies)
        elif self.kind == "file":
            self._send_file(image, copies)
        else:
            raise PrinterError(f"{self.name}: bilinmeyen yazıcı türü {self.kind!r}")

    def _send_tcp(self, payload: bytes) -> None:
        if not self.host:
            raise PrinterError(f"{self.name}: 'host' tanımlı değil.")
        try:
            with socket.create_connection((self.host, self.port), timeout=10) as s:
                s.sendall(payload)
        except OSError as e:
            raise PrinterError(f"{self.name} ({self.host}:{self.port}) yazıcısına bağlanılamadı: {e}") from None

    def _lp(self, options: list[str], payload: bytes) -> None:
        if not self.queue:
            raise PrinterError(f"{self.name}: 'queue' (CUPS kuyruk adı) tanımlı değil.")
        try:
            result = subprocess.run(
                ["lp", "-d", self.queue, *options], input=payload, capture_output=True, timeout=30
            )
        except FileNotFoundError:
            raise PrinterError("'lp' komutu bulunamadı. 'cups-client' paketini kurun.") from None
        if result.returncode != 0:
            msg = result.stderr.decode(errors="replace").strip()
            raise PrinterError(f"{self.name}: CUPS hatası: {msg}")

    def _send_cups_image(self, image: Image.Image, copies: int) -> None:
        w_mm = image.width / self.dpi * 25.4
        h_mm = image.height / self.dpi * 25.4
        buf = io.BytesIO()
        image.save(buf, format="PNG", dpi=(self.dpi, self.dpi))
        self._lp(
            [
                "-n", str(max(1, copies)),
                "-o", f"media=Custom.{w_mm:.1f}x{h_mm:.1f}mm",
                "-o", f"ppi={self.dpi}",
            ],
            buf.getvalue(),
        )

    def _send_file(self, image: Image.Image, copies: int) -> None:
        if not self.path:
            raise PrinterError(f"{self.name}: 'path' tanımlı değil.")
        path = Path(self.path)
        if path.suffix.lower() == ".png":
            image.save(path, dpi=(self.dpi, self.dpi))
        else:
            with path.open("a", encoding="ascii") as f:
                f.write(to_zpl(image, copies, self.compression))


def parse_printers(raw: dict) -> dict[str, Printer]:
    printers = {}
    for name, spec in raw.items():
        try:
            printer = Printer(name=name, **spec)
        except TypeError as e:
            raise PrinterError(f"{name}: geçersiz yazıcı tanımı: {e}") from None
        if printer.kind not in KINDS:
            raise PrinterError(f"{name}: 'kind' şunlardan biri olmalı: {', '.join(KINDS)}")
        printers[name] = printer
    return printers


PRINTERS_FILE = "yazicilar.json"


def printers_path(system: bool) -> Path:
    return config_dirs()[0 if system else 1] / PRINTERS_FILE


def read_printers_file(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PrinterError(f"{path}: JSON okunamadı: {e}") from None
    if not isinstance(raw, dict):
        raise PrinterError(f"{path}: yazıcı tanımları bir JSON nesnesi olmalı.")
    return raw


def load_printers() -> dict[str, Printer]:
    printers: dict[str, Printer] = {}
    for d in config_dirs():
        path = d / PRINTERS_FILE
        for name, printer in parse_printers(read_printers_file(path)).items():
            printer.source = path
            printers[name] = printer
    return printers


def printer_spec(printer: Printer) -> dict:
    """JSON'a yazılacak tanım: yalnızca varsayılandan farklı alanlar."""
    defaults = Printer(name="", kind=printer.kind)
    spec = {}
    for f in fields(Printer):
        if f.name in ("name", "source"):
            continue
        value = getattr(printer, f.name)
        if f.name == "kind" or value != getattr(defaults, f.name):
            spec[f.name] = value
    return spec


def updated_printers_json(path: Path, add: Printer | None = None, remove: str | None = None) -> str:
    """Dosyadaki diğer tanımlara dokunmadan ekler/siler; yeni içeriği döndürür."""
    raw = read_printers_file(path)
    if remove is not None:
        raw.pop(remove, None)
    if add is not None:
        raw[add.name] = printer_spec(add)
    parse_printers(raw)  # yazmadan önce doğrula
    return json.dumps(raw, ensure_ascii=False, indent=2) + "\n"


def write_printers_file(path: Path, content: str, use_pkexec: bool = False) -> None:
    """Yazıcı dosyasını yazar. Sistem dosyası için yetki yoksa pkexec kullanılabilir."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
        return
    except PermissionError:
        if not use_pkexec:
            raise PrinterError(
                f"{path} dosyasına yazma yetkiniz yok. Komutu sudo ile çalıştırın."
            ) from None
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tmp:
        tmp.write(content)
    os.chmod(tmp.name, 0o644)
    try:
        result = subprocess.run(
            ["pkexec", "install", "-D", "-m", "644", tmp.name, str(path)], capture_output=True, text=True
        )
    except FileNotFoundError:
        raise PrinterError("Yönetici yetkisi alınamadı: pkexec bulunamadı.") from None
    finally:
        os.unlink(tmp.name)
    if result.returncode in (126, 127):
        raise PrinterError("Yönetici parolası girilmedi; yazıcı kaydedilmedi.")
    if result.returncode != 0:
        raise PrinterError(f"{path} yazılamadı: {result.stderr.strip()}")

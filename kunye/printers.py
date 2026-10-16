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
import socket
import subprocess
from dataclasses import dataclass
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


def load_printers() -> dict[str, Printer]:
    printers: dict[str, Printer] = {}
    for d in config_dirs():
        path = d / "yazicilar.json"
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise PrinterError(f"{path}: JSON okunamadı: {e}") from None
            printers.update(parse_printers(raw))
    return printers

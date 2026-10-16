"""Şablonu yazıcı çözünürlüğünde 1 bitlik görüntüye çizer.

Her şey bitmap olarak çizilir: böylece önizleme basılan etiketle birebir
aynıdır ve yazıcının yerleşik fontunda olmayan Türkçe harfler sorun olmaz.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import code128
from .fill import MissingValueError, builtin_values
from .fill import fill as fill_placeholders
from .model import QR, Barcode, Box, Line, Template, Text

REGULAR_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "C:/Windows/Fonts/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
BOLD_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
MIN_SHRINK = 0.6  # sığdırmak için yazı en fazla bu orana kadar küçültülür


class RenderError(ValueError):
    pass


@lru_cache(maxsize=None)
def _font_path(bold: bool) -> str | None:
    env = os.environ.get("KUNYE_FONT_BOLD" if bold else "KUNYE_FONT")
    candidates = ([env] if env else []) + (BOLD_FONTS if bold else REGULAR_FONTS)
    return next((p for p in candidates if Path(p).is_file()), None)


@lru_cache(maxsize=256)
def _font(bold: bool, size_px: int) -> ImageFont.FreeTypeFont:
    path = _font_path(bold)
    if path is None:
        raise RenderError("Yazı tipi bulunamadı. 'fonts-dejavu-core' paketini kurun.")
    return ImageFont.truetype(path, size_px)


class Canvas:
    def __init__(self, template: Template, dpi: int):
        self.template = template
        self.dpm = dpi / 25.4
        self.width = self.d(template.width_mm)
        self.height = self.d(template.height_mm)
        self.image = Image.new("1", (self.width, self.height), 1)
        self.draw = ImageDraw.Draw(self.image)
        self.draw.fontmode = "1"

    def d(self, mm: float) -> int:
        return round(mm * self.dpm)

    def check_bounds(self, what: str, x0: int, y0: int, x1: int, y1: int) -> None:
        if x0 < 0 or y0 < 0 or x1 > self.width or y1 > self.height:
            raise RenderError(
                f"{what} etiketin dışına taşıyor. Veri çok uzun olabilir ya da "
                "şablondaki konum/boyut ayarlanmalı."
            )

    def text(self, el: Text, value: str) -> None:
        size = max(1, self.d(el.height_mm))
        font = _font(el.bold, size)
        if el.max_width_mm:
            limit = self.d(el.max_width_mm)
            min_size = max(1, int(size * MIN_SHRINK))
            while font.getlength(value) > limit and size > min_size:
                size -= 1
                font = _font(el.bold, size)
            if font.getlength(value) > limit:
                while value and font.getlength(value + "…") > limit:
                    value = value[:-1]
                value = value.rstrip() + "…"
        anchor = {"left": "la", "center": "ma", "right": "ra"}[el.align]
        self.draw.text((self.d(el.x_mm), self.d(el.y_mm)), value, font=font, fill=0, anchor=anchor)

    def barcode(self, el: Barcode, value: str) -> None:
        try:
            widths = code128.encode(value)
        except code128.Code128Error as e:
            raise RenderError(str(e)) from None
        module = max(1, self.d(el.module_mm))
        x, y = self.d(el.x_mm), self.d(el.y_mm)
        h = self.d(el.height_mm)
        total = sum(widths) * module
        self.check_bounds(f"Barkod ({value})", x, y, x + total, y + h)
        bar = True
        for w in widths:
            if bar:
                self.draw.rectangle([x, y, x + w * module - 1, y + h - 1], fill=0)
            x += w * module
            bar = not bar
        if el.human_readable:
            font = _font(False, max(8, self.d(2.5)))
            cx = self.d(el.x_mm) + total // 2
            self.draw.text((cx, y + h + self.d(0.5)), value, font=font, fill=0, anchor="ma")

    def qr(self, el: QR, value: str) -> None:
        try:
            import qrcode
        except ImportError:
            raise RenderError("QR kod için 'python3-qrcode' paketini kurun.") from None
        qr = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(value.encode("utf-8"))
        qr.make(fit=True)
        matrix = qr.get_matrix()
        module = max(1, self.d(el.module_mm))
        x0, y0 = self.d(el.x_mm), self.d(el.y_mm)
        size = len(matrix) * module
        self.check_bounds("QR kod", x0, y0, x0 + size, y0 + size)
        for r, row in enumerate(matrix):
            for c, dark in enumerate(row):
                if dark:
                    x, y = x0 + c * module, y0 + r * module
                    self.draw.rectangle([x, y, x + module - 1, y + module - 1], fill=0)

    def line(self, el: Line) -> None:
        pts = [(self.d(el.x1_mm), self.d(el.y1_mm)), (self.d(el.x2_mm), self.d(el.y2_mm))]
        self.draw.line(pts, fill=0, width=max(1, self.d(el.thickness_mm)))

    def box(self, el: Box) -> None:
        x, y = self.d(el.x_mm), self.d(el.y_mm)
        rect = [x, y, x + self.d(el.width_mm) - 1, y + self.d(el.height_mm) - 1]
        if el.filled:
            self.draw.rectangle(rect, fill=0)
        else:
            self.draw.rectangle(rect, outline=0, width=max(1, self.d(el.thickness_mm)))


def render(template: Template, values: dict[str, str], dpi: int = 203) -> Image.Image:
    """Etiketi tasarım (okuma) yönünde çizer."""
    values = {
        **builtin_values(),
        **{f.key: "" for f in template.fields},
        **{k: v for k, v in values.items() if v is not None},
    }
    canvas = Canvas(template, dpi)

    def fill(text: str) -> str:
        try:
            return fill_placeholders(text, values)
        except MissingValueError as e:
            raise RenderError(f"Şablonda tanımlanmamış alan kullanılmış: {{{e.args[0]}}}") from None
        except ValueError as e:
            raise RenderError(str(e)) from None

    for el in template.elements:
        if el.show_if and not values.get(el.show_if, "").strip():
            continue
        if isinstance(el, Text):
            canvas.text(el, fill(el.text))
        elif isinstance(el, (Barcode, QR)):
            data = fill(el.data)
            if not data.strip():
                continue  # boş barkod çizilmez; zorunlu alan denetimi basımı engeller
            if isinstance(el, Barcode):
                canvas.barcode(el, data)
            else:
                canvas.qr(el, data)
        elif isinstance(el, Line):
            canvas.line(el)
        elif isinstance(el, Box):
            canvas.box(el)
    return canvas.image


def for_print(image: Image.Image, rotate: int) -> Image.Image:
    """Tasarım görüntüsünü yazıcının besleme yönüne çevirir (saat yönünde)."""
    if rotate == 0:
        return image
    return image.rotate(-rotate, expand=True)

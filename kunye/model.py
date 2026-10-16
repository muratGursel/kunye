"""Etiket şablonu modeli.

Şablonlar JSON dosyalarıdır. Ölçüler milimetre cinsindendir ve etiketin
okunduğu yöndeki tasarım düzlemine göre verilir; yazıcıya gönderilirken
``rotate`` kadar döndürülür (bileklikler genellikle 90°).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROTATIONS = (0, 90, 180, 270)
ALIGNS = ("left", "center", "right")
SYMBOLOGIES = ("code128",)


class TemplateError(ValueError):
    pass


@dataclass
class Field:
    key: str
    label: str
    required: bool = False
    example: str = ""


@dataclass
class Text:
    x_mm: float
    y_mm: float
    height_mm: float
    text: str
    bold: bool = False
    align: str = "left"
    max_width_mm: float | None = None
    show_if: str | None = None


@dataclass
class Barcode:
    x_mm: float
    y_mm: float
    height_mm: float
    data: str
    symbology: str = "code128"
    module_mm: float = 0.25
    human_readable: bool = False
    show_if: str | None = None


@dataclass
class QR:
    x_mm: float
    y_mm: float
    data: str
    module_mm: float = 0.5
    show_if: str | None = None


@dataclass
class Line:
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float
    thickness_mm: float = 0.3
    show_if: str | None = None


@dataclass
class Box:
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    thickness_mm: float = 0.3
    filled: bool = False
    show_if: str | None = None


Element = Text | Barcode | QR | Line | Box

ELEMENT_TYPES: dict[str, type] = {
    "text": Text,
    "barcode": Barcode,
    "qr": QR,
    "line": Line,
    "box": Box,
}


@dataclass
class Template:
    id: str
    name: str
    width_mm: float
    height_mm: float
    description: str = ""
    rotate: int = 0
    fields: list[Field] = field(default_factory=list)
    elements: list[Element] = field(default_factory=list)
    path: Path | None = None

    def example_values(self) -> dict[str, str]:
        return {f.key: f.example for f in self.fields}

    def missing_fields(self, values: dict[str, str]) -> list[Field]:
        return [f for f in self.fields if f.required and not values.get(f.key, "").strip()]


def _build(cls: type, raw: dict[str, Any], where: str):
    try:
        return cls(**raw)
    except TypeError as e:
        raise TemplateError(f"{where}: geçersiz alan(lar): {e}") from None


def parse_template(raw: dict[str, Any], path: Path | None = None) -> Template:
    where = str(path) if path else "şablon"
    raw = dict(raw)
    fields = [_build(Field, f, f"{where} / alan") for f in raw.pop("fields", [])]
    elements: list[Element] = []
    for n, el in enumerate(raw.pop("elements", []), start=1):
        el = dict(el)
        kind = el.pop("type", None)
        cls = ELEMENT_TYPES.get(kind)
        if cls is None:
            raise TemplateError(f"{where}: {n}. elemanın türü bilinmiyor: {kind!r}")
        elements.append(_build(cls, el, f"{where} / {n}. eleman"))

    tpl = _build(Template, raw, where)
    tpl.fields, tpl.elements, tpl.path = fields, elements, path

    if tpl.rotate not in ROTATIONS:
        raise TemplateError(f"{where}: rotate 0, 90, 180 veya 270 olmalı.")
    if tpl.width_mm <= 0 or tpl.height_mm <= 0:
        raise TemplateError(f"{where}: etiket ölçüleri sıfırdan büyük olmalı.")
    for n, el in enumerate(tpl.elements, start=1):
        if isinstance(el, Text) and el.align not in ALIGNS:
            raise TemplateError(f"{where}: {n}. eleman: align {ALIGNS} değerlerinden biri olmalı.")
        if isinstance(el, Barcode) and el.symbology not in SYMBOLOGIES:
            raise TemplateError(f"{where}: {n}. eleman: desteklenmeyen barkod türü {el.symbology!r}.")
    return tpl


def load_template(path: Path) -> Template:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise TemplateError(f"{path}: JSON okunamadı: {e}") from None
    return parse_template(raw, path)

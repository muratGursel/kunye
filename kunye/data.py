"""Toplu basım için CSV okuma.

HBYS ve Excel çıktıları genellikle ';' ayraçlı ve Windows-1254
kodlamalı olur; ikisi de otomatik tanınır. Sütun başlıkları alan
anahtarlarına çevrilir: "Doğum Tarihi" -> "dogum_tarihi".
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

_ASCII = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def normalize_key(header: str) -> str:
    key = header.strip().translate(_ASCII).lower()
    return re.sub(r"[^a-z0-9]+", "_", key).strip("_")


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1254")


def read_csv(path: Path) -> list[dict[str, str]]:
    text = _decode(path.read_bytes())
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return []
    keys = [normalize_key(h) for h in rows[0]]
    return [{k: v.strip() for k, v in zip(keys, r)} for r in rows[1:]]

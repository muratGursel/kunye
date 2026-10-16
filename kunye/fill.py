"""Şablon metinlerindeki {alan|süzgeç} yer tutucularını doldurma."""

from __future__ import annotations

import re
from datetime import datetime

PLACEHOLDER = re.compile(r"\{([a-z0-9_]+)((?:\|[a-z_]+)*)\}")


class MissingValueError(KeyError):
    pass


def tr_upper(s: str) -> str:
    return s.replace("i", "İ").replace("ı", "I").upper()


def tr_lower(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


def mask(s: str, visible: int = 4) -> str:
    """KVKK: kimlik numarası gibi değerlerin yalnızca son hanelerini gösterir."""
    s = s.strip()
    if len(s) <= visible:
        return s
    return "*" * (len(s) - visible) + s[-visible:]


FILTERS = {
    "buyuk": tr_upper,
    "kucuk": tr_lower,
    "maskele": mask,
}


def builtin_values(now: datetime | None = None) -> dict[str, str]:
    now = now or datetime.now()
    return {"bugun": now.strftime("%d.%m.%Y"), "saat": now.strftime("%H:%M")}


def fill(text: str, values: dict[str, str]) -> str:
    def repl(m: re.Match) -> str:
        key, filters = m.group(1), m.group(2)
        if key not in values:
            raise MissingValueError(key)
        out = str(values[key])
        for name in filter(None, filters.split("|")):
            fn = FILTERS.get(name)
            if fn is None:
                raise ValueError(f"Bilinmeyen süzgeç: |{name}")
            out = fn(out)
        return out

    return PLACEHOLDER.sub(repl, text)

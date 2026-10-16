"""Hazır, sistem ve kullanıcı şablonlarını bulma."""

from __future__ import annotations

from pathlib import Path

from .config import config_dirs
from .model import Template, TemplateError, load_template

BUILTIN_DIR = Path(__file__).parent / "sablonlar"


def template_dirs() -> list[Path]:
    return [BUILTIN_DIR] + [d / "sablonlar" for d in config_dirs()]


def all_templates() -> dict[str, Template]:
    templates: dict[str, Template] = {}
    for d in template_dirs():
        if d.is_dir():
            for path in sorted(d.glob("*.json")):
                tpl = load_template(path)
                templates[tpl.id] = tpl
    return templates


def find_template(name: str) -> Template:
    """Şablon kimliği ya da .json dosya yolu kabul eder."""
    path = Path(name)
    if path.suffix == ".json" and path.is_file():
        return load_template(path)
    templates = all_templates()
    if name not in templates:
        known = ", ".join(sorted(templates)) or "(yok)"
        raise TemplateError(f"'{name}' adlı şablon bulunamadı. Mevcut şablonlar: {known}")
    return templates[name]

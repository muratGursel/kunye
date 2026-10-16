"""Sistem ve kullanıcı yapılandırma dizinleri.

Bilgi işlem, şablon ve yazıcı tanımlarını /etc/kunye altına koyarak (ör.
Lider Ahenk ile) tüm istemcilere dağıtabilir; kullanıcı dizinindeki
tanımlar aynı kimliğe sahip sistem tanımlarını geçersiz kılar.
"""

from __future__ import annotations

import os
from pathlib import Path

SYSTEM_DIR = Path(os.environ.get("KUNYE_SYSTEM_DIR", "/etc/kunye"))


def user_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "kunye"


def config_dirs() -> list[Path]:
    """Öncelik sırası artan: sonraki dizin öncekini geçersiz kılar."""
    return [SYSTEM_DIR, user_dir()]

"""1 bitlik görüntüyü Zebra ZPL II komutuna çevirir (^GF grafik alanı)."""

from __future__ import annotations

import base64
import binascii
import zlib

from PIL import Image


def _packed_rows(image: Image.Image) -> tuple[bytes, int]:
    """ZPL düzeninde (1 = siyah) satır satır paketlenmiş baytlar."""
    width, height = image.size
    padded_width = (width + 7) // 8 * 8
    if padded_width != width:
        canvas = Image.new("1", (padded_width, height), 1)
        canvas.paste(image.convert("1"), (0, 0))
        image = canvas
    raw = image.convert("1").tobytes()  # PIL: 1 = beyaz
    return bytes(b ^ 0xFF for b in raw), padded_width // 8


def graphic_field(image: Image.Image, compression: str = "z64") -> str:
    data, bytes_per_row = _packed_rows(image)
    total = len(data)
    if compression == "z64":
        b64 = base64.b64encode(zlib.compress(data, 9))
        crc = binascii.crc_hqx(b64, 0)
        payload = f":Z64:{b64.decode('ascii')}:{crc:04X}"
    elif compression == "hex":
        payload = data.hex().upper()
    else:
        raise ValueError(f"Bilinmeyen sıkıştırma: {compression}")
    return f"^GFA,{total},{total},{bytes_per_row},{payload}"


def to_zpl(image: Image.Image, copies: int = 1, compression: str = "z64") -> str:
    """Yazıcı yönündeki görüntüden tam bir ZPL etiketi üretir."""
    width, height = image.size
    return (
        "^XA\n"
        f"^PW{width}\n"
        f"^LL{height}\n"
        "^LH0,0\n"
        f"^FO0,0{graphic_field(image, compression)}^FS\n"
        f"^PQ{max(1, copies)}\n"
        "^XZ\n"
    )

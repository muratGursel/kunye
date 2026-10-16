import base64
import binascii
import re
import zlib

from PIL import Image, ImageDraw

from kunye.zpl import to_zpl


def sample_image():
    image = Image.new("1", (61, 20), 1)  # genişlik 8'in katı değil
    ImageDraw.Draw(image).rectangle([3, 2, 40, 10], fill=0)
    return image


def test_z64_roundtrip():
    image = sample_image()
    zpl = to_zpl(image, copies=3)
    m = re.search(r"\^GFA,(\d+),(\d+),(\d+),:Z64:([^:]+):([0-9A-F]{4})", zpl)
    total, _, per_row, b64, crc = m.groups()
    assert int(per_row) == 8 and int(total) == 8 * 20
    assert int(crc, 16) == binascii.crc_hqx(b64.encode(), 0)
    data = zlib.decompress(base64.b64decode(b64))
    for y in range(20):
        for x in range(64):
            bit = (data[y * 8 + x // 8] >> (7 - x % 8)) & 1
            black = x < 61 and image.getpixel((x, y)) == 0
            assert bit == black, (x, y)
    assert "^PQ3" in zpl and "^PW61" in zpl and "^LL20" in zpl


def test_hex_matches_z64():
    image = sample_image()
    hex_payload = re.search(r",([0-9A-F]+)\^FS", to_zpl(image, compression="hex")).group(1)
    b64 = re.search(r":Z64:([^:]+):", to_zpl(image)).group(1)
    assert bytes.fromhex(hex_payload) == zlib.decompress(base64.b64decode(b64))

import pytest

from kunye.catalog import all_templates
from kunye.model import Barcode
from kunye.render import RenderError, for_print, render

pyzbar = pytest.importorskip("pyzbar.pyzbar")

TEMPLATES = sorted(all_templates().values(), key=lambda t: t.id)


def decoded(image):
    return {r.data.decode() for r in pyzbar.decode(image.convert("L"))}


@pytest.mark.parametrize("dpi", [203, 300])
@pytest.mark.parametrize("tpl", TEMPLATES, ids=lambda t: t.id)
def test_barcodes_scan(tpl, dpi):
    values = tpl.example_values()
    image = for_print(render(tpl, values, dpi), tpl.rotate)
    found = decoded(image)
    for el in tpl.elements:
        if isinstance(el, Barcode):
            expected = el.data.strip("{}")
            assert values[expected] in found


def test_rotation_swaps_size():
    tpl = all_templates()["bileklik-yetiskin"]
    image = render(tpl, tpl.example_values(), 203)
    rotated = for_print(image, 90)
    assert rotated.size == (image.height, image.width)


def test_optional_elements_hidden():
    tpl = all_templates()["bileklik-yetiskin"]
    values = {**tpl.example_values(), "alerji": ""}
    with_allergy = render(tpl, tpl.example_values(), 203)
    without = render(tpl, values, 203)
    assert with_allergy.tobytes() != without.tobytes()


def test_long_barcode_overflow_is_error():
    tpl = all_templates()["tup-etiketi"]
    values = {**tpl.example_values(), "numune_no": "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
    with pytest.raises(RenderError):
        render(tpl, values, 203)


def test_empty_barcode_is_skipped():
    tpl = all_templates()["dosya-etiketi"]
    values = {**tpl.example_values(), "protokol_no": ""}
    image = render(tpl, values, 203)
    assert not decoded(image)


def test_unknown_placeholder_is_render_error():
    from kunye.model import parse_template
    tpl = parse_template({
        "id": "t", "name": "t", "width_mm": 50, "height_mm": 20,
        "elements": [{"type": "text", "x_mm": 1, "y_mm": 1, "height_mm": 3, "text": "{yok}"}],
    })
    with pytest.raises(RenderError, match="yok"):
        render(tpl, {}, 203)

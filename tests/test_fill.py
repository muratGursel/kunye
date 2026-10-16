import pytest

from kunye.fill import MissingValueError, fill, mask, tr_upper


def test_turkish_upper():
    assert tr_upper("şükrü ışık çiğdem") == "ŞÜKRÜ IŞIK ÇİĞDEM"


def test_mask():
    assert mask("12345678901") == "*******8901"
    assert mask("123") == "123"


def test_fill_with_filters():
    assert fill("{ad|buyuk} / {tc|maskele}", {"ad": "ilknur", "tc": "12345678901"}) == "İLKNUR / *******8901"


def test_missing_value():
    with pytest.raises(MissingValueError):
        fill("{yok}", {})

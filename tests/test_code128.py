from kunye import code128


def test_pattern_table():
    assert len(code128.PATTERNS) == 107
    assert len(set(code128.PATTERNS)) == 107
    for p in code128.PATTERNS[:-1]:
        assert len(p) == 6 and sum(map(int, p)) == 11
    assert sum(map(int, code128.PATTERNS[-1])) == 13


def test_numeric_uses_subset_c():
    values = code128.encode_values("2026104512")
    assert values[0] == code128.START_C
    assert len(values) == 1 + 5 + 1


def test_odd_digits_start_with_b():
    values = code128.encode_values("12345")
    assert values[:3] == [code128.START_B, ord("1") - 32, code128.CODE_C]


def test_rejects_non_ascii():
    import pytest
    with pytest.raises(code128.Code128Error):
        code128.encode_values("Şükrü")

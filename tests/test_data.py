from kunye.data import normalize_key, read_csv


def test_normalize_key():
    assert normalize_key(" Doğum Tarihi ") == "dogum_tarihi"
    assert normalize_key("TC Kimlik No") == "tc_kimlik_no"


def test_semicolon_cp1254(tmp_path):
    path = tmp_path / "hastalar.csv"
    path.write_bytes("Ad Soyad;Protokol No\nŞükrü Işık;2026104512\nGül Öz;2026104513\n".encode("cp1254"))
    rows = read_csv(path)
    assert rows == [
        {"ad_soyad": "Şükrü Işık", "protokol_no": "2026104512"},
        {"ad_soyad": "Gül Öz", "protokol_no": "2026104513"},
    ]

import base64
import ipaddress
import json
import re
import socketserver
import threading
import time
import zlib

import pytest
from PIL import Image

from kunye import cli, discovery
from kunye.catalog import all_templates
from kunye.printers import Printer, load_printers, printer_spec, updated_printers_json

pyzbar = pytest.importorskip("pyzbar.pyzbar")


class FakeZebra:
    """~HI sorgusuna yanıt veren ve gelen ZPL'yi biriktiren sahte yazıcı."""

    def __init__(self, model="ZD421-300dpi", dots=12):
        self.received = []
        outer = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                data = b""
                self.request.settimeout(1)
                try:
                    while chunk := self.request.recv(65536):
                        data += chunk
                        if data.strip() == b"~HI":
                            self.request.sendall(f"\x02{model},V84.20.21Z,{dots},8176KB\x03".encode())
                            data = b""
                except OSError:
                    pass
                if b"^XA" in data:
                    outer.received.append(data.decode("ascii"))

        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def wait(self, count=1, timeout=5.0):
        deadline = time.monotonic() + timeout
        while len(self.received) < count and time.monotonic() < deadline:
            time.sleep(0.05)
        return self.received

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def zebra():
    z = FakeZebra()
    yield z
    z.close()


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "kullanici"))
    monkeypatch.setattr("kunye.config.SYSTEM_DIR", tmp_path / "sistem")
    return tmp_path


def zpl_to_image(zpl: str) -> Image.Image:
    m = re.search(r"\^PW(\d+).*?\^GFA,(\d+),\d+,(\d+),:Z64:([^:]+):", zpl, re.S)
    width, total, per_row, b64 = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
    data = bytes(b ^ 0xFF for b in zlib.decompress(base64.b64decode(b64)))
    return Image.frombytes("1", (per_row * 8, total // per_row), data).crop((0, 0, width, total // per_row))


def test_parse_host_identification():
    assert discovery.parse_host_identification("\x02ZD421-203dpi,V84.20.21Z,8,8176KB\x03") == ("ZD421-203dpi", 203)
    assert discovery.parse_host_identification("\x02ZT410,V75.19.15Z,12,8176KB\x03") == ("ZT410", 300)


def test_parse_lpstat():
    out = ("device for Zebra_ZD421: usb://Zebra%20Technologies/ZTC%20ZD421-203dpi?serial=D4J1\n"
           "device for Ofis_HP: ipp://10.0.0.9/ipp/print\n")
    assert discovery.parse_lpstat_v(out) == {
        "Zebra_ZD421": "usb://Zebra%20Technologies/ZTC%20ZD421-203dpi?serial=D4J1",
        "Ofis_HP": "ipp://10.0.0.9/ipp/print",
    }


def ipp_response(printers):
    """CUPS'un CUPS-Get-Printers yanıtı biçiminde bayt dizisi."""
    a = discovery._ipp_attr
    data = b"\x02\x00\x00\x00\x00\x00\x00\x01\x01" + a(0x47, "attributes-charset", "utf-8")
    for p in printers:
        data += b"\x04" + b"".join(a(0x41 if k != "device-uri" else 0x45, k, v) for k, v in p.items())
    return data + b"\x03"


def test_ipp_request_and_parse(monkeypatch):
    req = discovery.ipp_get_printers_request()
    assert req[2:4] == b"\x40\x02" and b"printer-make-and-model" in req and req.endswith(b"\x03")
    resp = ipp_response([
        {"printer-name": "Zebra_ZD421", "device-uri": "usb://Zebra/ZD421?serial=1",
         "printer-make-and-model": "Zebra ZPL Label Printer"},
        {"printer-name": "Canon_iR_C3326", "device-uri": "implicitclass://Canon_iR_C3326/",
         "printer-make-and-model": "Canon iR C3326, driverless, cups-filters 1.28.17"},
    ])
    assert [p["printer-name"] for p in discovery.parse_ipp_printers(resp)] == ["Zebra_ZD421", "Canon_iR_C3326"]
    monkeypatch.setattr(discovery, "_ipp_post", lambda body: resp)
    zebra, canon = discovery.cups_printers()
    assert (zebra.kind, zebra.label) == ("zpl-cups", True)
    assert (canon.kind, canon.label, canon.model) == ("cups-image", False, "Canon iR C3326")


def test_ipp_error_status_falls_back_to_lpstat(monkeypatch):
    monkeypatch.setattr(discovery, "_ipp_post", lambda body: b"\x02\x00\x04\x01\x00\x00\x00\x01\x03")
    monkeypatch.setattr(discovery, "_run", lambda cmd, timeout=5: "device for TSC_TE210: usb://TSC/TE210\n")
    (tsc,) = discovery.cups_printers()
    assert (tsc.queue, tsc.label, tsc.kind) == ("TSC_TE210", True, "cups-image")


def test_parse_avahi():
    out = ("+;eth0;IPv4;ZTC\\032ZD421-300dpi;_pdl-datastream._tcp;local\n"
           "=;eth0;IPv4;ZTC\\032ZD421-300dpi;_pdl-datastream._tcp;local;zd421.local;10.10.5.21;9100;\"ty=ZTC ZD421\"\n")
    (found,) = discovery.parse_avahi(out)
    assert (found.host, found.port, found.dpi, found.zebra) == ("10.10.5.21", 9100, 300, True)


def test_zebra_identify_and_scan(zebra):
    assert discovery.zebra_identify("127.0.0.1", zebra.port) == ("ZD421-300dpi", 300)
    found = discovery.scan_network([ipaddress.ip_network("127.0.0.1/32")], port=zebra.port)
    assert [(f.host, f.dpi) for f in found] == [("127.0.0.1", 300)]


def test_scan_ignores_non_zebra():
    # 9100 açık ama ~HI'ye yanıt vermeyen (ofis yazıcısı gibi) bir sunucu
    class Silent(socketserver.BaseRequestHandler):
        def handle(self):
            self.request.recv(100)

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Silent)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        assert discovery.scan_network([ipaddress.ip_network("127.0.0.1/32")], port=port) == []
    finally:
        server.shutdown()
        server.server_close()


def test_manual_address_unreachable():
    with pytest.raises(ValueError, match="bağlanılamadı|yanıt vermiyor"):
        discovery.manual_network_printer("127.0.0.1:1")


def test_updated_json_keeps_other_printers(tmp_path):
    path = tmp_path / "yazicilar.json"
    path.write_text(json.dumps({"eski": {"kind": "file", "path": "/tmp/x.zpl", "ozel": 1}}), encoding="utf-8")
    with pytest.raises(Exception):  # dosyada geçersiz tanım varsa yazmadan reddet
        updated_printers_json(path, add=Printer(name="yeni", kind="zpl-tcp", host="10.0.0.5"))
    path.write_text(json.dumps({"eski": {"kind": "file", "path": "/tmp/x.zpl"}}), encoding="utf-8")
    raw = json.loads(updated_printers_json(path, add=Printer(name="yeni", kind="zpl-tcp", host="10.0.0.5", dpi=300)))
    assert raw == {
        "eski": {"kind": "file", "path": "/tmp/x.zpl"},
        "yeni": {"kind": "zpl-tcp", "dpi": 300, "host": "10.0.0.5"},
    }
    assert json.loads(updated_printers_json(path, remove="eski")) == {}


def test_spec_omits_source():
    p = Printer(name="a", kind="zpl-tcp", host="h")
    p.source = __import__("pathlib").Path("/etc/kunye/yazicilar.json")
    assert printer_spec(p) == {"kind": "zpl-tcp", "host": "h"}


def test_cli_add_detects_dpi_and_test_print_scans(zebra, config, capsys):
    assert cli.main(["yazici-ekle", "acil", "--ag", f"127.0.0.1:{zebra.port}", "--aciklama", "Acil"]) == 0
    printer = load_printers()["acil"]
    assert (printer.kind, printer.dpi, printer.port, printer.description) == ("zpl-tcp", 300, zebra.port, "Acil")
    assert printer.source == config / "kullanici" / "kunye" / "yazicilar.json"

    assert cli.main(["deneme", "acil", "tup-etiketi"]) == 0
    (zpl,) = zebra.wait()
    image = zpl_to_image(zpl)
    assert image.width == round(50 * 300 / 25.4)  # 300 dpi'da çizildi
    codes = {r.data.decode() for r in pyzbar.decode(image.convert("L"))}
    assert all_templates()["tup-etiketi"].example_values()["numune_no"] in codes

    assert cli.main(["yazici-sil", "acil"]) == 0
    assert "acil" not in load_printers()


def test_cli_add_system_scope(zebra, config):
    assert cli.main(["yazici-ekle", "lab", "--ag", f"127.0.0.1:{zebra.port}", "--sistem"]) == 0
    assert load_printers()["lab"].source == config / "sistem" / "yazicilar.json"


def test_test_values_hide_names():
    for tpl in all_templates().values():
        values = tpl.test_values()
        for key in ("ad_soyad", "anne_adi"):
            if key in values:
                assert values[key] == "DENEME BASKISI"


@pytest.mark.parametrize("model,label", [
    ("Zebra ZPL Label Printer", True),
    ("TSC TE210", True),
    ("Brother QL-820NWB", True),
    ("Godex G500", True),
    # Pardus 25 test makinesindeki gerçek ofis yazıcıları
    ("Canon iR C3326 UFR II", False),
    ("Hewlett-Packard HP Color LaserJet MFP M277n", False),
    ("Kyocera Kyocera ECOSYS MA3500cix (KPDL)", False),
    ("UTAX_TA UTAX_TA P-4035 MFP (KPDL)", False),
    ("Lexmark International Lexmark MX410de", False),
    ("RICOH RICOH SP 377SFNwX", False),
])
def test_label_printer_classification(model, label):
    assert discovery.is_label_printer(model) is label


def test_local_networks_skip_virtual(monkeypatch):
    monkeypatch.setattr(discovery, "_run", lambda cmd, timeout=5: (
        "2: enp0s31f6    inet 10.81.227.4/24 brd 10.81.227.255 scope global enp0s31f6\n"
        "3: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0\n"
        "5: br-6278a4769e62    inet 172.19.0.1/16 scope global br-6278a4769e62\n"
        "9: tun0    inet 172.25.30.129/32 scope global tun0\n"
        "2: enp0s31f6    inet 192.168.10.4/16 scope global enp0s31f6\n"
    ))
    assert [str(n) for n in discovery.local_networks()] == ["10.81.227.0/24", "192.168.10.0/24"]

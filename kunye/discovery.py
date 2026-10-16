"""Yazıcı bulma: CUPS kuyrukları, mDNS (Avahi) ve ağda Zebra taraması.

Bulunan yazıcılar kullanıcıya liste halinde sunulur; seçilen kayıttan
yazıcı tanımı (Printer) üretilir.
"""

from __future__ import annotations

import ipaddress
import os
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

ZPL_PORT = 9100
SCAN_TIMEOUT = 0.4
SCAN_WORKERS = 64
MAX_SCAN_HOSTS = 254  # yalnızca kendi /24 ağı taranır


@dataclass
class Found:
    """Bulunmuş, henüz tanımlanmamış bir yazıcı."""

    kind: str  # "zpl-tcp", "zpl-cups" ya da "cups-image"
    model: str
    source: str  # "cups", "mdns", "tarama", "elle"
    host: str | None = None
    port: int = ZPL_PORT
    queue: str | None = None
    dpi: int | None = None
    zebra: bool = False
    label: bool = False  # etiket yazıcısı (Zebra, TSC, Godex, Brother QL…); ofis yazıcısı değil

    @property
    def title(self) -> str:
        return self.model or self.queue or self.host or "Yazıcı"

    @property
    def subtitle(self) -> str:
        where = {
            "cups": f"Bu bilgisayarda kurulu · {self.queue}",
            "mdns": f"Ağ · {self.host}",
            "tarama": f"Ağ · {self.host}",
            "elle": f"Ağ · {self.host}",
        }[self.source]
        parts = [where]
        if self.dpi:
            parts.append(f"{self.dpi} dpi")
        parts.append("Zebra (ZPL)" if self.zebra else "Yazıcı sürücüsüyle")
        return " · ".join(parts)

    def suggested_name(self) -> str:
        base = self.queue or self.model or self.host or "yazici"
        m = re.search(r"(Z[DTMQ]\w*\d{3}\w*|HC\d+|GK\d+|GX\d+|TLP\d+)", base, re.I)
        if m:
            base = m.group(1)
        slug = re.sub(r"[^a-z0-9]+", "-", base.lower().translate(_ASCII)).strip("-")
        return slug or "yazici"


_ASCII = str.maketrans("çğıöşü", "cgiosu")


def _run(cmd: list[str], timeout: float = 5) -> str:
    env = {**os.environ, "LC_ALL": "C", "LANG": "C"}  # çıktı dilinden bağımsız ayrıştırma
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    return r.stdout if r.returncode == 0 else ""


LABEL_BRANDS = re.compile(
    r"zebra|ztc|\btsc\b|godex|brother[ _-]?(ql|td)|citizen|\bsato\b|honeywell|intermec|datamax|"
    r"argox|bixolon|xprinter|dymo|label|etiket",
    re.I,
)
VIRTUAL_INTERFACES = ("docker", "br-", "veth", "virbr", "lxc", "podman", "tun", "tap", "wg", "zt")


def is_label_printer(*texts: str | None) -> bool:
    return bool(LABEL_BRANDS.search(" ".join(t for t in texts if t)))


def is_zebra(*texts: str | None) -> bool:
    joined = " ".join(t for t in texts if t).lower()
    return "zebra" in joined or "ztc" in joined or "zpl" in joined


def dpi_from_text(*texts: str | None) -> int | None:
    m = re.search(r"(203|300|600)\s*dpi", " ".join(t for t in texts if t), re.I)
    return int(m.group(1)) if m else None


# --- CUPS --------------------------------------------------------------------

def parse_lpstat_v(text: str) -> dict[str, str]:
    """`lpstat -v` çıktısı: kuyruk adı -> aygıt adresi."""
    queues = {}
    for line in text.splitlines():
        m = re.match(r"device for (\S+):\s*(\S+)", line.strip())
        if m:
            queues[m.group(1)] = m.group(2)
    return queues


CUPS_SOCKET = "/run/cups/cups.sock"
IPP_ATTRIBUTES = ("printer-name", "printer-make-and-model", "device-uri")


def _ipp_attr(tag: int, name: str, value: str) -> bytes:
    n, v = name.encode(), value.encode()
    return bytes([tag]) + len(n).to_bytes(2, "big") + n + len(v).to_bytes(2, "big") + v


def ipp_get_printers_request() -> bytes:
    """CUPS-Get-Printers (0x4002) isteği: tek seferde bütün kuyruklar."""
    body = b"\x02\x00\x40\x02\x00\x00\x00\x01\x01"
    body += _ipp_attr(0x47, "attributes-charset", "utf-8")
    body += _ipp_attr(0x48, "attributes-natural-language", "en")
    body += _ipp_attr(0x44, "requested-attributes", IPP_ATTRIBUTES[0])
    for name in IPP_ATTRIBUTES[1:]:
        body += _ipp_attr(0x44, "", name)  # aynı özniteliğin ek değeri
    return body + b"\x03"


def parse_ipp_printers(data: bytes) -> list[dict[str, str]]:
    """IPP yanıtındaki her yazıcı grubunu {öznitelik: değer} olarak döndürür."""
    status = int.from_bytes(data[2:4], "big")
    if status > 0x00FF:
        raise OSError(f"CUPS IPP hatası 0x{status:04x}")
    printers, current, name, i = [], None, "", 8
    while i < len(data):
        tag = data[i]
        i += 1
        if tag == 0x03:
            break
        if tag < 0x10:  # yeni öznitelik grubu
            current = {} if tag == 0x04 else None
            if current is not None:
                printers.append(current)
            continue
        n = int.from_bytes(data[i:i + 2], "big")
        name = data[i + 2:i + 2 + n].decode() or name
        i += 2 + n
        v = int.from_bytes(data[i:i + 2], "big")
        value = data[i + 2:i + 2 + v]
        i += 2 + v
        if current is not None and name not in current:
            current[name] = value.decode("utf-8", errors="replace")
    return printers


def _ipp_post(body: bytes) -> bytes:
    import http.client

    class UnixConnection(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect(CUPS_SOCKET)

    errors = []
    for conn in (UnixConnection("localhost", timeout=5), http.client.HTTPConnection("localhost", 631, timeout=5)):
        try:
            conn.request("POST", "/", body, {"Content-Type": "application/ipp"})
            resp = conn.getresponse()
            if resp.status == 200:
                return resp.read()
            errors.append(f"HTTP {resp.status}")
        except OSError as e:
            errors.append(str(e))
        finally:
            conn.close()
    raise OSError("; ".join(errors))


def _cups_queue_info() -> list[tuple[str, str, str]]:
    """(kuyruk, adres, model). Önce tek IPP isteği; olmazsa lpstat -v (model olmadan)."""
    try:
        return [(p.get("printer-name", ""), p.get("device-uri", ""), p.get("printer-make-and-model", ""))
                for p in parse_ipp_printers(_ipp_post(ipp_get_printers_request())) if p.get("printer-name")]
    except (OSError, ValueError, IndexError):
        return [(q, uri, "") for q, uri in parse_lpstat_v(_run(["lpstat", "-v"])).items()]


def cups_printers() -> list[Found]:
    found = []
    for queue, uri, model in _cups_queue_info():
        model = model.split(", driverless")[0]  # cups-browsed eki: "…, driverless, cups-filters 1.28"
        zebra = is_zebra(queue, uri, model)
        found.append(Found(
            kind="zpl-cups" if zebra else "cups-image",
            model=model if model and model.lower() not in ("local raw printer", "raw queue") else queue,
            source="cups",
            queue=queue,
            dpi=dpi_from_text(queue, uri, model),
            zebra=zebra,
            label=zebra or is_label_printer(queue, uri, model),
        ))
    return found


# --- mDNS --------------------------------------------------------------------

def parse_avahi(text: str) -> list[Found]:
    """`avahi-browse -rtp _pdl-datastream._tcp` çıktısı (ham 9100 yazıcıları)."""
    found, seen = [], set()
    for line in text.splitlines():
        f = line.split(";")
        if len(f) < 9 or f[0] != "=" or f[2] != "IPv4":
            continue
        name, host, port = f[3].replace("\\032", " "), f[7], int(f[8])
        if (host, port) in seen:
            continue
        seen.add((host, port))
        txt = ";".join(f[9:])
        zebra = is_zebra(name, txt)
        found.append(Found(
            kind="zpl-tcp", model=name, source="mdns", host=host, port=port,
            dpi=dpi_from_text(name, txt), zebra=zebra, label=zebra or is_label_printer(name, txt),
        ))
    return found


def mdns_printers() -> list[Found]:
    return parse_avahi(_run(["avahi-browse", "-rtp", "_pdl-datastream._tcp"], timeout=4))


# --- Zebra sorgusu ve ağ taraması -------------------------------------------

def parse_host_identification(text: str) -> tuple[str, int | None]:
    """Zebra ~HI yanıtı: <STX>ZD421-203dpi,V84.20.21Z,8,8176KB<ETX>."""
    body = text.strip().strip("\x02\x03").strip()
    parts = body.split(",")
    model = parts[0].strip() if parts else ""
    dpi = dpi_from_text(model)
    if dpi is None and len(parts) > 2:
        dpi = {"8": 203, "12": 300, "24": 600}.get(parts[2].strip())
    return model, dpi


def zebra_identify(host: str, port: int = ZPL_PORT, timeout: float = 2.0) -> tuple[str, int | None] | None:
    """Yazıcıya ~HI gönderir. Zebra değilse ya da yanıt yoksa None."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.sendall(b"~HI\r\n")
            data = b""
            while b"\x03" not in data and len(data) < 512:
                chunk = s.recv(256)
                if not chunk:
                    break
                data += chunk
    except OSError:
        return None
    if b"\x02" not in data:
        return None
    return parse_host_identification(data.decode("ascii", errors="replace"))


def check_port(host: str, port: int = ZPL_PORT, timeout: float = 3.0) -> str | None:
    """Bağlantı kurulabiliyorsa None, kurulamıyorsa Türkçe hata."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return None
    except socket.timeout:
        return f"{host}:{port} yanıt vermiyor (zaman aşımı). IP adresini ve yazıcının açık olduğunu kontrol edin."
    except OSError as e:
        return f"{host}:{port} adresine bağlanılamadı: {e.strerror or e}"


def local_networks() -> list[ipaddress.IPv4Network]:
    """Bilgisayarın bağlı olduğu ağlar; büyük ağlarda yalnızca kendi /24'ü."""
    nets = []
    for line in _run(["ip", "-4", "-o", "addr", "show", "scope", "global"]).splitlines():
        m = re.search(r"^\d+:\s+(\S+)\s+inet (\d+\.\d+\.\d+\.\d+)/(\d+)", line)
        if not m or m.group(1).startswith(VIRTUAL_INTERFACES):
            continue  # Docker köprüleri, VPN tünelleri vb. taranmaz
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/(\d+)", line)
        prefix = max(int(m.group(2)), 24)
        net = ipaddress.ip_network(f"{m.group(1)}/{prefix}", strict=False)
        if net not in nets:
            nets.append(net)
    return nets


def scan_network(networks: list[ipaddress.IPv4Network] | None = None, port: int = ZPL_PORT,
                 progress=None) -> list[Found]:
    """Ağda 9100 portu açık ve ~HI sorgusuna yanıt veren Zebra yazıcıları bulur."""
    hosts = [str(h) for net in (networks or local_networks()) for h in net.hosts()][: MAX_SCAN_HOSTS * 4]

    def probe(host: str) -> Found | None:
        try:
            with socket.create_connection((host, port), timeout=SCAN_TIMEOUT):
                pass
        except OSError:
            return None
        ident = zebra_identify(host, port)
        if not ident:
            return None  # 9100 açık ama Zebra değil (ör. ofis yazıcısı)
        model, dpi = ident
        return Found(kind="zpl-tcp", model=model, source="tarama", host=host, port=port,
                     dpi=dpi, zebra=True, label=True)

    found = []
    with ThreadPoolExecutor(SCAN_WORKERS) as pool:
        for n, result in enumerate(pool.map(probe, hosts), start=1):
            if result:
                found.append(result)
            if progress:
                progress(n, len(hosts))
    return found


def manual_network_printer(address: str) -> Found:
    """Kullanıcının yazdığı 'IP' ya da 'IP:port' adresinden kayıt üretir."""
    host, _, port_text = address.strip().partition(":")
    if not host:
        raise ValueError("IP adresi boş olamaz.")
    port = int(port_text) if port_text else ZPL_PORT
    error = check_port(host, port)
    if error:
        raise ValueError(error)
    ident = zebra_identify(host, port)
    model, dpi = ident if ident else ("", None)
    return Found(kind="zpl-tcp", model=model or host, source="elle", host=host, port=port,
                 dpi=dpi, zebra=bool(ident), label=True)


def to_printer(found: Found, name: str, dpi: int, description: str = "", zpl: bool | None = None):
    """Seçilen kayıttan yazıcı tanımı. zpl verilirse CUPS yazıcısının dilini belirler."""
    from .printers import Printer

    kind = found.kind
    if found.source == "cups" and zpl is not None:
        kind = "zpl-cups" if zpl else "cups-image"
    return Printer(
        name=name.strip(), kind=kind, dpi=dpi, description=description.strip(),
        host=found.host if kind == "zpl-tcp" else None,
        port=found.port if kind == "zpl-tcp" else 9100,
        queue=found.queue if kind != "zpl-tcp" else None,
    )

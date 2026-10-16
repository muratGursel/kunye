"""Gerçek yazıcı olmadan deneme için sahte Zebra yazıcı.

~HI sorgusuna bir Zebra gibi yanıt verir; gelen ZPL etiketlerini dosyaya
yazar. Kullanım: python3 tools/sahte_zebra.py [--port 9100] [--model ZD421-300dpi] [--cikti etiketler.zpl]
"""

import argparse
import socketserver
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9100)
    ap.add_argument("--model", default="ZD421-203dpi")
    ap.add_argument("--cikti", default="sahte-zebra.zpl")
    args = ap.parse_args()
    out = Path(args.cikti)

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            data = b""
            self.request.settimeout(2)
            try:
                while True:
                    chunk = self.request.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                    if data.strip() == b"~HI":
                        dots = {"203": 8, "300": 12, "600": 24}.get(args.model.split("-")[-1][:3], 8)
                        self.request.sendall(f"\x02{args.model},V84.20.21Z,{dots},8176KB\x03".encode())
                        data = b""
            except OSError:
                pass
            if b"^XA" in data:
                with out.open("ab") as f:
                    f.write(data)
                print(f"etiket alındı: {data.count(b'^XA')} ({len(data)} bayt)", flush=True)

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((args.host, args.port), Handler) as server:
        print(f"sahte Zebra {args.model} dinliyor: {args.host}:{args.port}", flush=True)
        server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Arayüzü senaryo üzerinden sürer ve her adımda pencere görüntüsü alır.

Ekransız kullanım (Broadway):
    gtk4-broadwayd :7 &
    GDK_BACKEND=broadway BROADWAY_DISPLAY=:7 python3 tools/gui_snapshot.py /tmp/kunye-shots
Yazıcı olarak ``file`` türünde bir yazıcı tanımlanmış olmalıdır (XDG_CONFIG_HOME).
"""

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Graphene", "1.0")

from gi.repository import GLib, Graphene, Gtk  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kunye.gui.app import KunyeApp  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "kunye-shots")
OUT.mkdir(parents=True, exist_ok=True)
CSV = OUT / "hastalar.csv"


def snap(window: Gtk.Widget, name: str) -> bool:
    # Pencerenin kendisi boyanamıyor; diyalogları da içeren iç kapsayıcı alınır
    target = window.get_first_child()
    w, h = target.get_width(), target.get_height()
    snapshot = Gtk.Snapshot()
    window.snapshot_child(target, snapshot)
    try:
        node = snapshot.to_node()
    except TypeError:  # PyGObject < 3.44 bazı GskRenderNode türlerini çeviremez
        node = None
    if node is None:
        return False
    rect = Graphene.Rect().init(0, 0, w, h)
    window.get_renderer().render_texture(node, rect).save_to_png(str(OUT / f"{name}.png"))
    print("görüntü:", name, flush=True)
    return True


def shot(window: Gtk.Widget, name: str, tries: int = 15):
    """Broadway yalnızca istemci kare istediğinde çizer: çizilene kadar yeniden dene."""
    for _ in range(tries):
        if snap(window, name):
            return
        window.queue_draw()
        yield 200
    print(f"görüntü alınamadı: {name}", flush=True)


def select(win, template_id: str) -> None:
    i = next(n for n, t in enumerate(win.templates) if t.id == template_id)
    win.sidebar.select_row(win.sidebar.get_row_at_index(i))


def fill(win, values: dict) -> None:
    for key, value in values.items():
        win.entries[key].set_text(value)


def scenario(win):
    yield 400
    yield from shot(win, "01-acilis")

    select(win, "bileklik-yetiskin")
    fill(win, win.template.example_values())
    yield 600
    yield from shot(win, "02-bileklik-dolu")

    win.print_label()
    yield 800
    print("form temizlendi mi:", not any(win.values().values()), flush=True)
    yield from shot(win, "03-basim-sonrasi")

    fill(win, {"ad_soyad": "Ayşe Çelik"})
    win.print_label()
    yield 500
    print("eksik alanla önizleme:", "var" if win.picture.get_paintable() else "yok", flush=True)
    yield from shot(win, "04-eksik-alan")

    select(win, "tup-etiketi")
    fill(win, {"ad_soyad": "İsmail Ağaoğlu", "numune_no": "ÇĞ-123", "tup_turu": "Hemogram"})
    yield 500
    yield from shot(win, "05-gecersiz-barkod")

    print("geçersiz barkodda önizleme:", "var (HATA)" if win.picture.get_paintable() else "temizlendi", flush=True)
    win.entries["numune_no"].set_text("2610160099")
    yield 500
    yield from shot(win, "06-tup-dolu")

    select(win, "bileklik-yetiskin")
    CSV.write_bytes(
        "Ad Soyad;Protokol No;Doğum Tarihi;Alerji\n"
        "Ayşe Çelik;2026104600;01.02.1970;\n"
        "İsmail Ağaoğlu;2026104601;05.06.1985;Lateks\n".encode("cp1254")
    )
    win._on_csv_chosen(CSV)
    yield 600
    yield from shot(win, "07-toplu-onay")
    print("ONAY BEKLENİYOR", flush=True)
    yield 1000
    yield from shot(win, "08-toplu-sonrasi")

    win.get_application().quit()


def main():
    app = KunyeApp()

    def on_activate(_app):
        win = app.props.active_window
        steps = scenario(win)

        def step():
            try:
                GLib.timeout_add(next(steps), step)
            except StopIteration:
                pass
            return False

        GLib.idle_add(step)

    app.connect_after("activate", on_activate)
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())

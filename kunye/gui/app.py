"""Künye GTK uygulaması."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from .. import __version__  # noqa: E402
from . import compat  # noqa: E402
from .window import KunyeWindow  # noqa: E402

APP_ID = "io.github.muratgursel.Kunye"

CSS = """
.kunye-preview { background-color: white; }
"""


class KunyeApp(Adw.Application):
    def __init__(self):
        flags = getattr(Gio.ApplicationFlags, "DEFAULT_FLAGS", Gio.ApplicationFlags.FLAGS_NONE)
        super().__init__(application_id=APP_ID, flags=flags)
        self.connect("activate", self._on_activate)
        self.connect("startup", self._on_startup)

    def _on_startup(self, _app) -> None:
        provider = Gtk.CssProvider()
        if hasattr(provider, "load_from_string"):  # GTK 4.12+
            provider.load_from_string(CSS)
        else:
            provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self._add_action("print", lambda: self._main_window().print_label(), ["<Control>p"])
        self._add_action("clear", lambda: self._main_window().clear_form(), ["<Control>l"])
        self._add_action("printers", lambda: self._main_window().show_printers())
        self._add_action("about", self._show_about)
        self._add_action("quit", self.quit, ["<Control>q"])

    def _add_action(self, name, callback, accels=None) -> None:
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", lambda *_: callback())
        self.add_action(action)
        if accels:
            self.set_accels_for_action(f"app.{name}", accels)

    def menu_model(self) -> Gio.Menu:
        menu = Gio.Menu()
        menu.append("Yazıcılar…", "app.printers")
        menu.append("Formu Temizle", "app.clear")
        menu.append("Künye Hakkında", "app.about")
        menu.append("Çıkış", "app.quit")
        return menu

    def _main_window(self) -> KunyeWindow:
        return next(w for w in self.get_windows() if isinstance(w, KunyeWindow))

    def _on_activate(self, _app) -> None:
        window = self.props.active_window or KunyeWindow(self)
        window.present()

    def _show_about(self) -> None:
        compat.about(
            self.props.active_window,
            application_name="Künye",
            application_icon=APP_ID,
            version=__version__,
            comments="Hasta bilekliği, barkod ve etiket basıcı",
            license_type=Gtk.License.GPL_3_0,
        )


def main() -> int:
    # PyGObject GTK'yı içe aktarırken başlatır; ekran yoksa varsayılan ekran boş kalır
    if Gdk.Display.get_default() is None:
        print(
            "kunye-arayuz: grafik ekran bulunamadı. Arayüzü masaüstü oturumunda açın; "
            "uçbirimden basmak için 'kunye' komutunu kullanın.",
            file=sys.stderr,
        )
        return 1
    return KunyeApp().run(sys.argv[:1])

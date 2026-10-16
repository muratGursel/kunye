"""Yazıcıları listeleme, ekleme (bulunanlar listesinden seçerek) ve silme."""

from __future__ import annotations

import shutil
import subprocess
import threading
from typing import Callable

from gi.repository import Adw, GLib, Gtk

from .. import discovery
from ..model import Template
from ..printers import (
    Printer,
    PrinterError,
    load_printers,
    printers_path,
    updated_printers_json,
    write_printers_file,
)
from ..render import for_print, render
from . import compat

DPIS = [203, 300, 600]
KIND_NAMES = {
    "zpl-tcp": "Ağ · Zebra (ZPL)",
    "zpl-cups": "Bu bilgisayarda · Zebra (ZPL)",
    "cups-image": "Bu bilgisayarda · yazıcı sürücüsüyle",
    "file": "Dosyaya yazar (deneme)",
}


def run_in_thread(work: Callable, done: Callable) -> None:
    """work() arka planda çalışır; done(sonuç, hata) arayüz iş parçacığında çağrılır."""

    def target():
        try:
            result, error = work(), None
        except Exception as e:  # arayüze Türkçe mesaj olarak iletilir
            result, error = None, e
        GLib.idle_add(lambda: done(result, error) and False)

    threading.Thread(target=target, daemon=True).start()


def scope_label(printer: Printer) -> str:
    if printer.source and printer.source == printers_path(system=True):
        return "Bu bilgisayardaki herkes"
    return "Yalnızca siz"


def send_test_label(printer: Printer, template: Template) -> None:
    printer.send(for_print(render(template, template.test_values(), printer.dpi), template.rotate))


def printer_settings_command() -> list[str] | None:
    """Pardus'un yazıcı ayarları uygulaması (XFCE ya da GNOME)."""
    if shutil.which("system-config-printer"):
        return ["system-config-printer"]
    if shutil.which("gnome-control-center"):
        return ["gnome-control-center", "printers"]
    return None


def margins(widget: Gtk.Widget, value: int) -> None:
    for side in ("top", "bottom", "start", "end"):
        getattr(widget, f"set_margin_{side}")(value)


class PrintersWindow(Adw.Window):
    """Tanımlı yazıcılar: deneme baskısı, silme ve yeni yazıcı ekleme."""

    def __init__(self, parent: Gtk.Window, template_getter: Callable[[], Template | None],
                 on_changed: Callable[[str | None], None]):
        super().__init__(transient_for=parent, modal=True, title="Yazıcılar")
        self.set_default_size(680, 560)
        self.template_getter = template_getter
        self.on_changed = on_changed

        self.toasts = Adw.ToastOverlay()
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        add = Gtk.Button(label="Yazıcı Ekle")
        add.add_css_class("suggested-action")
        add.connect("clicked", lambda *_: self.open_add())
        header.pack_end(add)
        root.append(header)
        self.toasts.set_child(root)
        self.set_content(self.toasts)

        scroller = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        margins(self.body, 24)
        clamp = Adw.Clamp(maximum_size=720)
        clamp.set_child(self.body)
        scroller.set_child(clamp)
        root.append(scroller)
        self.refresh()

    def refresh(self) -> None:
        child = self.body.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.body.remove(child)
            child = nxt
        try:
            printers = list(load_printers().values())
        except PrinterError as e:
            compat.alert(self, "Yazıcı tanımları okunamadı", str(e))
            printers = []

        if not printers:
            status = Adw.StatusPage(
                icon_name="printer-symbolic",
                title="Henüz yazıcı yok",
                description="Künye bu bilgisayarda kurulu yazıcıları ve ağdaki Zebra yazıcıları "
                            "bulup listeler; listeden seçmeniz yeterli.",
            )
            button = Gtk.Button(label="Yazıcı Ekle", halign=Gtk.Align.CENTER)
            button.add_css_class("suggested-action")
            button.add_css_class("pill")
            button.connect("clicked", lambda *_: self.open_add())
            status.set_child(button)
            self.body.append(status)
            return

        group = Adw.PreferencesGroup(
            title="Tanımlı Yazıcılar",
            description="Deneme baskısı, ana pencerede seçili şablonla ve “DENEME BASKISI” adıyla basılır.",
        )
        for printer in printers:
            target = printer.host or printer.queue or printer.path or ""
            parts = [KIND_NAMES.get(printer.kind, printer.kind), target, f"{printer.dpi} dpi", scope_label(printer)]
            title = f"{printer.name} — {printer.description}" if printer.description else printer.name
            row = Adw.ActionRow(title=title, subtitle=" · ".join(p for p in parts if p))
            row.add_prefix(Gtk.Image(icon_name="printer-symbolic"))

            test = Gtk.Button(label="Deneme Baskısı", valign=Gtk.Align.CENTER)
            test.connect("clicked", self._on_test, printer)
            row.add_suffix(test)

            delete = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                                tooltip_text="Yazıcıyı sil")
            delete.add_css_class("flat")
            delete.connect("clicked", self._on_delete, printer)
            row.add_suffix(delete)
            group.add(row)
        self.body.append(group)

    def toast(self, text: str) -> None:
        self.toasts.add_toast(Adw.Toast(title=text))

    def open_add(self) -> None:
        AddPrinterWindow(self, self._on_added).present()

    def _on_added(self, printer: Printer) -> None:
        self.refresh()
        self.on_changed(printer.name)
        toast = Adw.Toast(title=f"“{printer.name}” eklendi.", button_label="Deneme Baskısı", timeout=10)
        toast.connect("button-clicked", lambda *_: self._on_test(None, printer))
        self.toasts.add_toast(toast)

    def _on_test(self, _button, printer: Printer) -> None:
        template = self.template_getter()
        if template is None:
            return

        def done(_result, error):
            if error:
                compat.alert(self, "Deneme baskısı gönderilemedi", str(error))
            else:
                self.toast(f"Deneme etiketi ({template.name}) gönderildi. Barkodu okutarak kontrol edin.")

        run_in_thread(lambda: send_test_label(printer, template), done)

    def _on_delete(self, _button, printer: Printer) -> None:
        path = printer.source
        use_pkexec = path == printers_path(system=True)

        def done(_result, error):
            if error:
                compat.alert(self, "Silinemedi", str(error))
                return
            self.refresh()
            self.on_changed(None)
            self.toast(f"“{printer.name}” silindi.")

        def remove():
            run_in_thread(
                lambda: write_printers_file(path, updated_printers_json(path, remove=printer.name), use_pkexec),
                done,
            )

        compat.confirm(self, "Yazıcı silinsin mi?",
                       f"“{printer.name}” Künye'den kaldırılacak. Yazıcının kendisine bir şey yapılmaz.",
                       "Sil", remove)


class AddPrinterWindow(Adw.Window):
    """Bulunan yazıcılar listesinden seçerek yazıcı ekleme."""

    def __init__(self, parent: Gtk.Window, on_added: Callable[[Printer], None]):
        super().__init__(transient_for=parent, modal=True, title="Yazıcı Ekle")
        self.set_default_size(680, 720)
        self.on_added = on_added
        self.found: list[discovery.Found] = []
        self.rows: list[tuple[Adw.ActionRow, Gtk.Image, discovery.Found]] = []
        self.top_rows: list[Gtk.Widget] = []  # gruba doğrudan eklenen satırlar
        self.selected: discovery.Found | None = None
        self._pending = 0  # süren arama sayısı
        try:
            self.existing = load_printers()
        except PrinterError:
            self.existing = {}

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar(show_end_title_buttons=False, show_start_title_buttons=False)
        cancel = Gtk.Button(label="Vazgeç")
        cancel.connect("clicked", lambda *_: self.close())
        header.pack_start(cancel)
        self.add_button = Gtk.Button(label="Ekle", sensitive=False)
        self.add_button.add_css_class("suggested-action")
        self.add_button.connect("clicked", lambda *_: self._on_add())
        header.pack_end(self.add_button)
        root.append(header)
        self.set_content(root)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        margins(box, 24)
        clamp = Adw.Clamp(maximum_size=720)
        clamp.set_child(box)
        scroller = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.set_child(clamp)
        root.append(scroller)

        # Hata en üstte: elle adres girilince aşağıda kalıp gözden kaçmasın
        self.error = Gtk.Label(wrap=True, xalign=0, visible=False)
        self.error.add_css_class("error")
        box.append(self.error)

        # Bulunanlar
        self.found_group = Adw.PreferencesGroup(title="Bulunan Yazıcılar",
                                                description="Eklemek istediğiniz yazıcıya tıklayın.")
        suffix = Gtk.Box(spacing=6)
        self.spinner = Gtk.Spinner()
        suffix.append(self.spinner)
        self.scan_button = Gtk.Button(label="Ağı Tara", valign=Gtk.Align.CENTER,
                                      tooltip_text="Yerel ağda Zebra yazıcı ara (9100 portu)")
        self.scan_button.connect("clicked", lambda *_: self._scan())
        suffix.append(self.scan_button)
        self.found_group.set_header_suffix(suffix)
        self.empty_row = Adw.ActionRow(title="Aranıyor…")
        self.found_group.add(self.empty_row)
        box.append(self.found_group)

        # Elle ekleme
        manual = Adw.PreferencesGroup(title="Listede yok mu?")
        self.address = Adw.EntryRow(title="Ağ yazıcısının IP adresi (ör. 10.10.5.21)")
        self.address.set_show_apply_button(True)
        self.address.connect("apply", lambda *_: self._connect_manual())
        self.address.connect("entry-activated", lambda *_: self._connect_manual())
        manual.add(self.address)
        command = printer_settings_command()
        usb = Adw.ActionRow(
            title="USB ile bağlı yazıcı",
            subtitle="Listede görünmüyorsa önce Pardus'un yazıcı ayarlarından ekleyin, sonra burada "
                     "“Yeniden Ara”ya basın.",
        )
        if command:
            settings = Gtk.Button(label="Yazıcı Ayarları", valign=Gtk.Align.CENTER)
            settings.connect("clicked", lambda *_: subprocess.Popen(command))
            usb.add_suffix(settings)
        again = Gtk.Button(label="Yeniden Ara", valign=Gtk.Align.CENTER)
        again.connect("clicked", lambda *_: self._discover())
        usb.add_suffix(again)
        manual.add(usb)
        box.append(manual)

        # Ayarlar
        self.settings_group = Adw.PreferencesGroup(title="Ayarlar", sensitive=False)
        self.name_row = Adw.EntryRow(title="Ad (ör. acil-zebra)")
        self.desc_row = Adw.EntryRow(title="Açıklama (ör. Acil triyaj)")
        self.dpi_row = Adw.ComboRow(title="Çözünürlük", model=Gtk.StringList.new([f"{d} dpi" for d in DPIS]))
        self.lang_row = Adw.ComboRow(
            title="Yazıcı dili",
            model=Gtk.StringList.new(["Zebra (ZPL)", "Yazıcı sürücüsüyle (diğer markalar)"]),
            visible=False,
        )
        self.everyone = Gtk.Switch(active=True, valign=Gtk.Align.CENTER)
        everyone_row = Adw.ActionRow(title="Bu bilgisayardaki herkes kullanabilsin",
                                     subtitle="Yönetici parolası sorulur")
        everyone_row.add_suffix(self.everyone)
        everyone_row.set_activatable_widget(self.everyone)
        for row in (self.name_row, self.desc_row, self.dpi_row, self.lang_row, everyone_row):
            self.settings_group.add(row)
        box.append(self.settings_group)
        self.scroller = scroller

        self._discover()

    # --- bulma ---------------------------------------------------------------

    def _busy(self, busy: bool) -> None:
        self.spinner.set_spinning(busy)

    def _discover(self) -> None:
        # CUPS anında yanıt verir; mDNS birkaç saniye sürer: ayrı ayrı, geldikçe listele
        self._pending += 2
        self._busy(True)
        run_in_thread(discovery.cups_printers, self._on_found)
        run_in_thread(discovery.mdns_printers, self._on_found)

    def _scan(self) -> None:
        self._pending += 1
        self._busy(True)
        self.scan_button.set_sensitive(False)
        self.scan_button.set_label("Taranıyor…")

        def progress(n, total):
            if n % 16 == 0 or n == total:
                GLib.idle_add(lambda: self.scan_button.set_label(f"Taranıyor… %{n * 100 // total}") and False)

        def done(result, error):
            self.scan_button.set_label("Ağı Tara")
            self.scan_button.set_sensitive(True)
            self._on_found(result, error)
            if not error and not result:
                self._show_error("Ağda Zebra yazıcı bulunamadı. Yazıcının açık ve aynı ağda olduğunu "
                                 "kontrol edin ya da IP adresini elle girin.")

        run_in_thread(lambda: discovery.scan_network(progress=progress), done)

    def _on_found(self, result, error) -> None:
        self._pending = max(0, self._pending - 1)
        self._busy(self._pending > 0)
        if error:
            self._show_error(str(error))
            return
        for f in result or []:
            if not any((f.host, f.port, f.queue) == (o.host, o.port, o.queue) for o in self.found):
                self.found.append(f)
        self._rebuild_list()

    def _configured_name(self, f: discovery.Found) -> str | None:
        for p in self.existing.values():
            if (f.source == "cups" and p.queue == f.queue) or (f.host and p.host == f.host and p.port == f.port):
                return p.name
        return None

    def _make_row(self, f: discovery.Found) -> Adw.ActionRow:
        existing = self._configured_name(f)
        subtitle = f.subtitle + (f" · zaten ekli: {existing}" if existing else "")
        row = Adw.ActionRow(title=f.title, subtitle=subtitle, activatable=not existing,
                            sensitive=not existing)
        row.add_prefix(Gtk.Image(icon_name="network-wired-symbolic" if f.host else "printer-symbolic"))
        check = Gtk.Image(icon_name="object-select-symbolic", visible=f is self.selected)
        row.add_suffix(check)
        row.connect("activated", lambda _r: self._select(f))
        self.rows.append((row, check, f))
        return row

    def _rebuild_list(self) -> None:
        for row in self.top_rows:
            self.found_group.remove(row)
        self.top_rows, self.rows = [], []

        labels = sorted((f for f in self.found if f.label), key=lambda f: (not f.zebra, f.title.lower()))
        others = sorted((f for f in self.found if not f.label), key=lambda f: f.title.lower())

        self.empty_row.set_visible(not labels)
        self.empty_row.set_title("Etiket yazıcısı bulunamadı")
        self.empty_row.set_subtitle("Ağdaki Zebra yazıcılar için “Ağı Tara”ya basın ya da IP adresini girin.")
        for f in labels:
            row = self._make_row(f)
            self.found_group.add(row)
            self.top_rows.append(row)

        # Ofis yazıcıları kalabalık olabilir; etiket yazıcılarını gölgelemesin
        if others:
            expander = Adw.ExpanderRow(
                title=f"Diğer yazıcılar ({len(others)})",
                subtitle="Ofis yazıcıları; bileklik ve etiket basmak için genellikle uygun değildir",
            )
            for f in others:
                expander.add_row(self._make_row(f))
            self.found_group.add(expander)
            self.top_rows.append(expander)

    def _connect_manual(self) -> None:
        address = self.address.get_text().strip()
        if not address:
            return
        self._pending += 1
        self._busy(True)
        self.error.set_visible(False)

        def done(result, error):
            self._pending = max(0, self._pending - 1)
            self._busy(self._pending > 0)
            if error:
                self._show_error(str(error))
                return
            self._on_found([result], None)
            self._select(next(f for f in self.found if (f.host, f.port) == (result.host, result.port)))
            if not result.zebra:
                self._show_error("Bağlantı kuruldu ama yazıcı Zebra olarak tanınmadı. "
                                 "ZPL desteklemiyorsa etiket basılamaz; deneme baskısıyla kontrol edin.")

        run_in_thread(lambda: discovery.manual_network_printer(address), done)

    # --- seçim ve ekleme -----------------------------------------------------

    def _select(self, f: discovery.Found) -> None:
        self.selected = f
        self.error.set_visible(False)
        for _row, check, other in self.rows:
            check.set_visible(other is f)
        self.settings_group.set_sensitive(True)
        name = f.suggested_name()
        n = 2
        while name in self.existing:
            name = f"{f.suggested_name()}-{n}"
            n += 1
        self.name_row.set_text(name)
        self.dpi_row.set_selected(DPIS.index(f.dpi) if f.dpi in DPIS else 0)
        self.lang_row.set_visible(f.source == "cups")
        self.lang_row.set_selected(0 if f.zebra else 1)
        self.add_button.set_sensitive(True)

    def _show_error(self, text: str) -> None:
        self.error.set_label(text)
        self.error.set_visible(True)
        self.scroller.get_vadjustment().set_value(0)  # hata en üstte, görünür olsun

    def _on_add(self) -> None:
        f = self.selected
        name = self.name_row.get_text().strip()
        if not f:
            return
        if not name:
            self._show_error("Yazıcıya bir ad verin.")
            return
        if name in self.existing:
            self._show_error(f"“{name}” adında bir yazıcı zaten var; başka bir ad seçin.")
            return
        zpl = self.lang_row.get_selected() == 0 if f.source == "cups" else None
        printer = discovery.to_printer(f, name, DPIS[self.dpi_row.get_selected()],
                                       self.desc_row.get_text(), zpl)
        system = self.everyone.get_active()
        path = printers_path(system)
        self.add_button.set_sensitive(False)

        def done(_result, error):
            self.add_button.set_sensitive(True)
            if error:
                self._show_error(str(error))
                return
            printer.source = path
            self.on_added(printer)
            self.close()

        run_in_thread(lambda: write_printers_file(path, updated_printers_json(path, add=printer), system), done)

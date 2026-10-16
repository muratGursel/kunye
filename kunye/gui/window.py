"""Künye ana penceresi."""

from __future__ import annotations

import threading
from pathlib import Path

from gi.repository import Adw, Gdk, GLib, Gtk
from PIL import Image

from ..catalog import all_templates
from ..data import read_csv
from ..model import Template
from ..printers import Printer, PrinterError, load_printers
from ..render import for_print, render
from . import compat

PREVIEW_DELAY_MS = 150
PREVIEW_DPI = 203
LONG_LABEL_RATIO = 4  # bileklik gibi uzun etiketlerde önizleme dolu kısma kırpılır


def to_texture(image: Image.Image) -> Gdk.Texture:
    rgb = image.convert("RGB")
    data = GLib.Bytes.new(rgb.tobytes())
    return Gdk.MemoryTexture.new(rgb.width, rgb.height, Gdk.MemoryFormat.R8G8B8, data, rgb.width * 3)


def crop_for_preview(image: Image.Image, dpi: int) -> Image.Image:
    if image.width / image.height < LONG_LABEL_RATIO:
        return image
    bbox = Image.eval(image.convert("L"), lambda p: 255 - p).getbbox()
    if not bbox:
        return image
    right = min(image.width, bbox[2] + round(8 * dpi / 25.4))
    return image.crop((0, 0, right, image.height))


class KunyeWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Künye")
        self.set_default_size(1100, 720)

        self.templates: list[Template] = sorted(all_templates().values(), key=lambda t: t.name)
        self.printers: list[Printer] = []
        self.template: Template | None = None
        self.entries: dict[str, Adw.EntryRow] = {}
        self._preview_source = 0
        self._busy = False
        self._toast: Adw.Toast | None = None

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toasts.set_child(root)

        self.title = Adw.WindowTitle(title="Künye", subtitle="")
        header = Adw.HeaderBar(title_widget=self.title)
        menu = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text="Ana menü")
        menu.set_menu_model(app.menu_model())
        header.pack_end(menu)
        # Asıl eylem kaydırmadan her zaman görünür olsun
        self.print_button = Gtk.Button(label="Bas")
        self.print_button.add_css_class("suggested-action")
        self.print_button.set_tooltip_text("Etiketi bas (Ctrl+P)")
        self.print_button.connect("clicked", lambda *_: self.print_label())
        header.pack_end(self.print_button)
        root.append(header)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True)
        paned.set_position(270)
        paned.set_shrink_start_child(False)
        paned.set_resize_start_child(False)
        root.append(paned)

        paned.set_start_child(self._build_sidebar())
        paned.set_end_child(self._build_content())

        if self.templates:
            self.sidebar.select_row(self.sidebar.get_row_at_index(0))

    # --- yerleşim -----------------------------------------------------------

    def _build_sidebar(self) -> Gtk.Widget:
        self.sidebar = Gtk.ListBox(selection_mode=Gtk.SelectionMode.BROWSE)
        self.sidebar.add_css_class("navigation-sidebar")
        for tpl in self.templates:
            row = Adw.ActionRow(title=tpl.name, subtitle=f"{tpl.width_mm:g} × {tpl.height_mm:g} mm")
            row.template = tpl
            self.sidebar.append(row)
        self.sidebar.connect("row-selected", self._on_template_selected)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.set_child(self.sidebar)
        return scroller

    def _build_content(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(24)

        # Önizleme
        self.picture = Gtk.Picture(can_shrink=True, height_request=170)
        self.picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        frame.add_css_class("card")
        frame.add_css_class("kunye-preview")
        for side in ("top", "bottom", "start", "end"):
            getattr(self.picture, f"set_margin_{side}")(12)
        frame.append(self.picture)
        box.append(frame)

        self.preview_error = Gtk.Label(wrap=True, xalign=0, visible=False)
        self.preview_error.add_css_class("error")
        box.append(self.preview_error)

        # Form alanları şablon seçilince doldurulur
        self.fields_group = Adw.PreferencesGroup(title="Etiket Bilgileri")
        box.append(self.fields_group)

        # Basım ayarları
        print_group = Adw.PreferencesGroup(title="Basım")
        self.no_printer_row = Adw.ActionRow(
            title="Yazıcı tanımlı değil",
            subtitle="Bu bilgisayardaki ve ağdaki yazıcılar listelenir; birini seçmeniz yeterli.",
        )
        add_printer = Gtk.Button(label="Yazıcı Ekle", valign=Gtk.Align.CENTER)
        add_printer.add_css_class("suggested-action")
        add_printer.connect("clicked", lambda *_: self.add_printer())
        self.no_printer_row.add_suffix(add_printer)
        print_group.add(self.no_printer_row)

        self.printer_row = Adw.ComboRow(title="Yazıcı")
        manage = Gtk.Button(icon_name="emblem-system-symbolic", valign=Gtk.Align.CENTER,
                            tooltip_text="Yazıcıları yönet")
        manage.add_css_class("flat")
        manage.connect("clicked", lambda *_: self.show_printers())
        self.printer_row.add_suffix(manage)
        self.printer_row.connect("notify::selected", lambda *_: self.schedule_preview())
        print_group.add(self.printer_row)

        self.copies = Gtk.SpinButton.new_with_range(1, 20, 1)
        self.copies.set_valign(Gtk.Align.CENTER)
        copies_row = Adw.ActionRow(title="Kopya sayısı")
        copies_row.add_suffix(self.copies)
        print_group.add(copies_row)
        box.append(print_group)

        # Düğmeler
        buttons = Gtk.Box(spacing=12, halign=Gtk.Align.END)
        clear = Gtk.Button(label="Temizle")
        clear.connect("clicked", lambda *_: self.clear_form())
        png = Gtk.Button(label="PNG Kaydet…")
        png.connect("clicked", lambda *_: self.save_png())
        self.batch_button = Gtk.Button(label="CSV'den Toplu Bas…")
        self.batch_button.connect("clicked", lambda *_: self.batch_print())
        for b in (clear, png, self.batch_button):
            buttons.append(b)
        box.append(buttons)
        self.reload_printers()

        clamp = Adw.Clamp(maximum_size=920)
        clamp.set_child(box)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.set_child(clamp)
        return scroller

    # --- şablon ve form ------------------------------------------------------

    def _on_template_selected(self, _list, row) -> None:
        if row is None:
            return
        self.template = row.template
        self.picture.set_paintable(None)
        if self._toast:  # önceki şablona ait uyarı yanıltmasın
            self._toast.dismiss()
            self._toast = None
        self.title.set_subtitle(self.template.name)
        self.fields_group.set_description(self.template.description)

        for entry in self.entries.values():
            self.fields_group.remove(entry)
        self.entries = {}
        for f in self.template.fields:
            entry = Adw.EntryRow(title=f"{f.label} *" if f.required else f.label)
            entry.connect("changed", self._on_field_changed)
            entry.connect("entry-activated", self._focus_next)
            self.fields_group.add(entry)
            self.entries[f.key] = entry
        self.schedule_preview()

    def _on_field_changed(self, entry: Adw.EntryRow) -> None:
        entry.remove_css_class("error")
        self.schedule_preview()

    def _focus_next(self, entry: Adw.EntryRow) -> None:
        # Barkod okuyucular Enter gönderir: sıradaki alana geç
        rows = list(self.entries.values())
        i = rows.index(entry)
        if i + 1 < len(rows):
            rows[i + 1].grab_focus()

    def values(self) -> dict[str, str]:
        return {key: entry.get_text().strip() for key, entry in self.entries.items()}

    def clear_form(self) -> None:
        for entry in self.entries.values():
            entry.set_text("")
        if self.entries:
            next(iter(self.entries.values())).grab_focus()

    # --- yazıcılar -----------------------------------------------------------

    def reload_printers(self, select: str | None = None) -> None:
        current = select or (self.selected_printer().name if self.selected_printer() else None)
        try:
            self.printers = list(load_printers().values())
        except PrinterError as e:
            self.printers = []
            message = str(e)  # 'e' except bloğundan sonra silinir
            GLib.idle_add(lambda: compat.alert(self, "Yazıcı tanımları okunamadı", message) and False)
        names = [f"{p.name} — {p.description}" if p.description else p.name for p in self.printers]
        self.printer_row.set_model(Gtk.StringList.new(names))
        for i, p in enumerate(self.printers):
            if p.name == current:
                self.printer_row.set_selected(i)
        has = bool(self.printers)
        self.no_printer_row.set_visible(not has)
        self.printer_row.set_visible(has)
        self.print_button.set_sensitive(has and not self._busy)
        self.batch_button.set_sensitive(has)
        self.schedule_preview()

    def show_printers(self):
        from .printers import PrintersWindow

        window = PrintersWindow(self, lambda: self.template, self.reload_printers)
        window.present()
        return window

    def add_printer(self):
        from .printers import AddPrinterWindow

        def added(printer):
            self.reload_printers(printer.name)
            self.toast(f"“{printer.name}” eklendi.", "Deneme Baskısı", lambda: self.test_print(printer))

        window = AddPrinterWindow(self, added)
        window.present()
        return window

    def test_print(self, printer: Printer) -> None:
        from .printers import run_in_thread, send_test_label

        template = self.template

        def done(_result, error):
            if error:
                compat.alert(self, "Deneme baskısı gönderilemedi", str(error))
            else:
                self.toast(f"Deneme etiketi ({template.name}) gönderildi. Barkodu okutarak kontrol edin.")

        run_in_thread(lambda: send_test_label(printer, template), done)

    def selected_printer(self) -> Printer | None:
        i = self.printer_row.get_selected()
        if not self.printers or not 0 <= i < len(self.printers):
            return None
        return self.printers[i]

    # --- önizleme ------------------------------------------------------------

    def schedule_preview(self) -> None:
        if self._preview_source:
            GLib.source_remove(self._preview_source)
        self._preview_source = GLib.timeout_add(PREVIEW_DELAY_MS, self._update_preview)

    def _update_preview(self) -> bool:
        self._preview_source = 0
        if not self.template:
            return False
        printer = self.selected_printer()
        dpi = printer.dpi if printer else PREVIEW_DPI
        try:
            image = render(self.template, self.values(), dpi)
        except Exception as e:  # önizleme her hatada ayakta kalmalı
            # Eski önizleme kalırsa başka hastanın etiketi görünebilir: temizle
            self.picture.set_paintable(None)
            self.preview_error.set_label(str(e))
            self.preview_error.set_visible(True)
            return False
        self.preview_error.set_visible(False)
        self.picture.set_paintable(to_texture(crop_for_preview(image, dpi)))
        return False

    # --- basım ---------------------------------------------------------------

    def _check_required(self) -> bool:
        values = self.values()
        missing = self.template.missing_fields(values)
        for f in missing:
            self.entries[f.key].add_css_class("error")
        if missing:
            self.entries[missing[0].key].grab_focus()
            self.toast("Eksik alan: " + ", ".join(f.label for f in missing))
        return not missing

    def print_label(self) -> None:
        printer = self.selected_printer()
        if self._busy or not self.template or not printer or not self._check_required():
            return
        try:
            image = for_print(render(self.template, self.values(), printer.dpi), self.template.rotate)
        except Exception as e:
            compat.alert(self, "Etiket hazırlanamadı", str(e))
            return
        copies = int(self.copies.get_value())
        self._run_print(printer, [image], copies, clear_after=True)

    def batch_print(self) -> None:
        if self.template and self.selected_printer():
            compat.open_file(self, "CSV Dosyası Seç", "CSV dosyaları", ["*.csv", "*.CSV", "*.txt"],
                             self._on_csv_chosen)

    def _on_csv_chosen(self, path: Path) -> None:
        tpl, printer = self.template, self.selected_printer()
        try:
            rows = read_csv(path)
        except (OSError, UnicodeDecodeError) as e:
            compat.alert(self, "CSV okunamadı", str(e))
            return
        if not rows:
            compat.alert(self, "CSV boş", f"{path.name} dosyasında kayıt bulunamadı.")
            return

        problems = []
        for n, row in enumerate(rows, start=1):
            missing = tpl.missing_fields(row)
            if missing:
                problems.append(f"{n}. satır: " + ", ".join(f.label for f in missing))
        if problems:
            more = f"\n… ve {len(problems) - 10} satır daha" if len(problems) > 10 else ""
            compat.alert(self, "Eksik bilgi var", "Zorunlu alanları boş satırlar:\n" + "\n".join(problems[:10]) + more)
            return

        try:
            images = [for_print(render(tpl, row, printer.dpi), tpl.rotate) for row in rows]
        except Exception as e:
            compat.alert(self, "Etiket hazırlanamadı", str(e))
            return

        copies = int(self.copies.get_value())
        compat.confirm(
            self,
            "Toplu basım",
            f"{path.name} dosyasından {len(images)} etiket ({copies} kopya) “{printer.name}” yazıcısına gönderilecek.",
            "Bas",
            lambda: self._run_print(printer, images, copies, clear_after=False),
        )

    def _run_print(self, printer: Printer, images: list[Image.Image], copies: int, clear_after: bool) -> None:
        self._busy = True
        self.print_button.set_sensitive(False)
        self.print_button.set_label("Gönderiliyor…")

        def work():
            error = None
            try:
                for image in images:
                    printer.send(image, copies)
            except PrinterError as e:
                error = str(e)
            GLib.idle_add(done, error)

        def done(error):
            self._busy = False
            self.print_button.set_sensitive(True)
            self.print_button.set_label("Bas")
            if error:
                compat.alert(self, "Yazıcıya gönderilemedi", error)
            else:
                self.toast(f"{len(images)} etiket “{printer.name}” yazıcısına gönderildi.")
                if clear_after:
                    self.clear_form()
            return False

        threading.Thread(target=work, daemon=True).start()

    def save_png(self) -> None:
        if not self.template:
            return
        name = f"{self.template.id}.png"
        compat.save_file(self, "Önizlemeyi Kaydet", name, self._on_png_chosen)

    def _on_png_chosen(self, path: Path) -> None:
        try:
            render(self.template, self.values(), 300).save(path, dpi=(300, 300))
        except Exception as e:
            compat.alert(self, "Kaydedilemedi", str(e))
            return
        self.toast(f"Kaydedildi: {path.name}")

    def toast(self, text: str, button: str | None = None, on_button=None) -> None:
        # Yeni bildirim eskisinin arkasında beklemesin
        if self._toast:
            self._toast.dismiss()
        self._toast = Adw.Toast(title=text)
        if button:
            self._toast.set_button_label(button)
            self._toast.set_timeout(10)
            self._toast.connect("button-clicked", lambda *_: on_button())
        self.toasts.add_toast(self._toast)

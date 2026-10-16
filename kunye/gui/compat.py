"""GTK 4.8 / libadwaita 1.2 (Pardus 23) ile yeni sürümler (Pardus 25) arası uyum."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from gi.repository import Adw, Gio, GLib, Gtk


def _filter(name: str, patterns: list[str]) -> Gtk.FileFilter:
    f = Gtk.FileFilter()
    f.set_name(name)
    for p in patterns:
        f.add_pattern(p)
    return f


def open_file(parent: Gtk.Window, title: str, filter_name: str, patterns: list[str],
              callback: Callable[[Path], None]) -> None:
    filt = _filter(filter_name, patterns)
    if hasattr(Gtk, "FileDialog"):
        dialog = Gtk.FileDialog(title=title)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filt)
        dialog.set_filters(filters)

        def done(d, result):
            try:
                file = d.open_finish(result)
            except GLib.Error:
                return
            callback(Path(file.get_path()))

        dialog.open(parent, None, done)
    else:
        chooser = Gtk.FileChooserNative(title=title, transient_for=parent, action=Gtk.FileChooserAction.OPEN)
        chooser.add_filter(filt)
        _run_native(chooser, callback)


def save_file(parent: Gtk.Window, title: str, initial_name: str,
              callback: Callable[[Path], None]) -> None:
    if hasattr(Gtk, "FileDialog"):
        dialog = Gtk.FileDialog(title=title, initial_name=initial_name)

        def done(d, result):
            try:
                file = d.save_finish(result)
            except GLib.Error:
                return
            callback(Path(file.get_path()))

        dialog.save(parent, None, done)
    else:
        chooser = Gtk.FileChooserNative(title=title, transient_for=parent, action=Gtk.FileChooserAction.SAVE)
        chooser.set_current_name(initial_name)
        _run_native(chooser, callback)


def _run_native(chooser: Gtk.FileChooserNative, callback: Callable[[Path], None]) -> None:
    def response(c, r):
        if r == Gtk.ResponseType.ACCEPT:
            callback(Path(c.get_file().get_path()))
        c.destroy()

    chooser.connect("response", response)
    chooser.show()


def confirm(parent: Gtk.Window, heading: str, body: str, ok_label: str,
            on_ok: Callable[[], None]) -> None:
    def response(_d, r):
        if r == "ok":
            on_ok()

    if hasattr(Adw, "AlertDialog"):
        dialog = Adw.AlertDialog(heading=heading, body=body)
    else:
        dialog = Adw.MessageDialog(transient_for=parent, modal=True, heading=heading, body=body)
    dialog.add_response("cancel", "Vazgeç")
    dialog.add_response("ok", ok_label)
    dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("ok")
    dialog.set_close_response("cancel")
    dialog.connect("response", response)
    if hasattr(Adw, "AlertDialog"):
        dialog.present(parent)
    else:
        dialog.present()


def alert(parent: Gtk.Window, heading: str, body: str) -> None:
    if hasattr(Adw, "AlertDialog"):
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("close", "Tamam")
        dialog.present(parent)
    else:
        dialog = Adw.MessageDialog(transient_for=parent, modal=True, heading=heading, body=body)
        dialog.add_response("close", "Tamam")
        dialog.present()


def about(parent: Gtk.Window, **props) -> None:
    if hasattr(Adw, "AboutDialog"):
        Adw.AboutDialog(**props).present(parent)
    else:
        Adw.AboutWindow(transient_for=parent, **props).present()

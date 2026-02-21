"""Mitt Schema Pro — Weekly visual schedule."""

import gettext
import json
import locale
from datetime import datetime, timedelta
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from mittschema import __version__
from mittschema.export import show_export_dialog

try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    pass
for d in [Path(__file__).parent.parent / "po", Path("/usr/share/locale")]:
    if d.is_dir():
        locale.bindtextdomain("mittschema", str(d))
        gettext.bindtextdomain("mittschema", str(d))
        break
gettext.textdomain("mittschema")
_ = gettext.gettext

APP_ID = "se.danielnylander.mittschema"

WEEKDAYS = [_("Monday"), _("Tuesday"), _("Wednesday"), _("Thursday"), _("Friday"), _("Saturday"), _("Sunday")]
DEFAULT_COLORS = ["#3584e4", "#2ec27e", "#e66100", "#9141ac", "#e01b24", "#f5c211", "#62a0ea"]


def _config_dir():
    p = Path(GLib.get_user_config_dir()) / "mittschema"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _load_schedule():
    path = _config_dir() / "schedule.json"
    if path.exists():
        try: return json.loads(path.read_text())
        except Exception: pass
    return {day: [] for day in WEEKDAYS}

def _save_schedule(schedule):
    (_config_dir() / "schedule.json").write_text(json.dumps(schedule, indent=2, ensure_ascii=False))


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("My Schedule Pro"))
        self.set_default_size(800, 600)
        self.schedule = _load_schedule()

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        header = Adw.HeaderBar()
        main_box.append(header)

        add_btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text=_("Add Activity"))
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add)
        header.pack_start(add_btn)

        export_btn = Gtk.Button(icon_name="document-save-symbolic", tooltip_text=_("Export (Ctrl+E)"))
        export_btn.connect("clicked", lambda *_: self._on_export())
        header.pack_end(export_btn)

        menu = Gio.Menu()
        menu.append(_("Export Schedule"), "win.export")
        menu.append(_("About My Schedule Pro"), "app.about")
        menu.append(_("Quit"), "app.quit")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        header.pack_end(menu_btn)

        ea = Gio.SimpleAction.new("export", None)
        ea.connect("activate", lambda *_: self._on_export())
        self.add_action(ea)

        ctrl = Gtk.EventControllerKey()
        ctrl.connect("key-pressed", self._on_key)
        self.add_controller(ctrl)

        # Week view
        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.week_box = Gtk.Box(spacing=4)
        self.week_box.set_homogeneous(True)
        self.week_box.set_margin_top(8)
        self.week_box.set_margin_start(8)
        self.week_box.set_margin_end(8)
        self.week_box.set_margin_bottom(8)
        scroll.set_child(self.week_box)
        main_box.append(scroll)

        self.status = Gtk.Label(label="", xalign=0)
        self.status.add_css_class("dim-label")
        self.status.set_margin_start(12)
        self.status.set_margin_bottom(4)
        main_box.append(self.status)
        GLib.timeout_add_seconds(1, lambda: (self.status.set_label(GLib.DateTime.new_now_local().format("%Y-%m-%d %H:%M:%S")), True)[-1])

        self._build_week()

    def _on_key(self, ctrl, keyval, keycode, state):
        if state & Gdk.ModifierType.CONTROL_MASK and keyval in (Gdk.KEY_e, Gdk.KEY_E):
            self._on_export()
            return True
        return False

    def _on_export(self):
        items = []
        for day, activities in self.schedule.items():
            for act in activities:
                items.append({"day": day, "time": act.get("time", ""), "activity": act.get("name", "")})
        show_export_dialog(self, items, _("My Schedule Pro"), lambda m: self.status.set_label(m))

    def _build_week(self):
        child = self.week_box.get_first_child()
        while child:
            nc = child.get_next_sibling()
            self.week_box.remove(child)
            child = nc

        for i, day in enumerate(WEEKDAYS):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            lbl = Gtk.Label(label=day)
            lbl.add_css_class("heading")
            col.append(lbl)

            sep = Gtk.Separator()
            col.append(sep)

            activities = self.schedule.get(day, [])
            for act in activities:
                card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                card.add_css_class("card")
                card.set_margin_top(2)
                card.set_margin_start(2)
                card.set_margin_end(2)
                t = Gtk.Label(label=act.get("time", ""), xalign=0)
                t.add_css_class("caption")
                card.append(t)
                n = Gtk.Label(label=act.get("name", ""), xalign=0, wrap=True)
                n.add_css_class("body")
                card.append(n)
                col.append(card)

            if not activities:
                empty = Gtk.Label(label=_("No activities"))
                empty.add_css_class("dim-label")
                empty.set_margin_top(20)
                col.append(empty)

            col.set_vexpand(True)
            self.week_box.append(col)

    def _on_add(self, *_):
        dialog = Adw.AlertDialog.new(_("Add Activity"), _("Add a new activity to your schedule"))

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        day_combo = Gtk.DropDown.new_from_strings(WEEKDAYS)
        box.append(day_combo)

        time_entry = Gtk.Entry()
        time_entry.set_placeholder_text(_("Time (e.g. 08:00)"))
        box.append(time_entry)

        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text(_("Activity name"))
        box.append(name_entry)

        dialog.set_extra_child(box)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("add", _("Add"))
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        def on_response(d, r):
            if r == "add" and name_entry.get_text().strip():
                day = WEEKDAYS[day_combo.get_selected()]
                if day not in self.schedule:
                    self.schedule[day] = []
                self.schedule[day].append({
                    "time": time_entry.get_text().strip(),
                    "name": name_entry.get_text().strip(),
                })
                self.schedule[day].sort(key=lambda a: a.get("time", ""))
                _save_schedule(self.schedule)
                self._build_week()
                self.status.set_label(_("Added: %s") % name_entry.get_text().strip())

        dialog.connect("response", on_response)
        dialog.present(self)


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.connect("activate", self._on_activate)

    def _on_activate(self, *_):
        win = self.props.active_window or MainWindow(self)
        a = Gio.SimpleAction(name="about"); a.connect("activate", self._on_about); self.add_action(a)
        qa = Gio.SimpleAction(name="quit"); qa.connect("activate", lambda *_: self.quit()); self.add_action(qa)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        win.present()

    def _on_about(self, *_):
        dialog = Adw.AboutDialog(
            application_name=_("My Schedule Pro"), application_icon=APP_ID, version=__version__,
            developer_name="Daniel Nylander", license_type=Gtk.License.GPL_3_0,
            website="https://www.autismappar.se",
            developers=["Daniel Nylander <daniel@danielnylander.se>"],
            comments=_("Weekly visual schedule with school integration"),
        )
        dialog.present(self.props.active_window)


def main():
    app = App()
    return app.run()

"""Mitt Schema - Weekly visual schedule."""
import sys, os, json, gettext, locale
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib, Gdk
from mittschema import __version__
from mittschema.accessibility import apply_large_text

TEXTDOMAIN = "mittschema"
for p in [os.path.join(os.path.dirname(__file__), "locale"), "/usr/share/locale"]:
    if os.path.isdir(p):
        gettext.bindtextdomain(TEXTDOMAIN, p)
        locale.bindtextdomain(TEXTDOMAIN, p)
        break
gettext.textdomain(TEXTDOMAIN)
_ = gettext.gettext

CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "mittschema")
SCHEDULE_FILE = os.path.join(CONFIG_DIR, "schedule.json")

DAYS = [_("Monday"), _("Tuesday"), _("Wednesday"), _("Thursday"), _("Friday"), _("Saturday"), _("Sunday")]
PERIODS = [_("Morning"), _("Afternoon"), _("Evening")]
DEFAULT_ACTIVITIES = [
    {"name": _("School"), "emoji": "\U0001f3eb"},
    {"name": _("Lunch"), "emoji": "\U0001f35d"},
    {"name": _("Homework"), "emoji": "\U0001f4da"},
    {"name": _("Play"), "emoji": "\U0001f3ae"},
    {"name": _("Dinner"), "emoji": "\U0001f37d"},
    {"name": _("Bath"), "emoji": "\U0001f6c1"},
    {"name": _("Sleep"), "emoji": "\U0001f634"},
    {"name": _("Exercise"), "emoji": "\U0001f3c3"},
    {"name": _("Reading"), "emoji": "\U0001f4d6"},
    {"name": _("Free time"), "emoji": "\u2b50"},
]

def _load_schedule():
    try:
        with open(SCHEDULE_FILE) as f: return json.load(f)
    except: return {d: {p: [] for p in range(3)} for d in range(7)}

def _save_schedule(s):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(SCHEDULE_FILE, "w") as f: json.dump(s, f, ensure_ascii=False, indent=2)


class ScheduleApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="se.danielnylander.mittschema",
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        apply_large_text()
        win = self.props.active_window or ScheduleWindow(application=self)
        win.present()

    def do_startup(self):
        Adw.Application.do_startup(self)
        for name, cb, accel in [
            ("quit", lambda *_: self.quit(), "<Control>q"),
            ("about", self._on_about, None),
            ("export", self._on_export, "<Control>e"),
        ]:
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", cb)
            self.add_action(a)
            if accel: self.set_accels_for_action(f"app.{name}", [accel])

    def _on_about(self, *_):
        d = Adw.AboutDialog(application_name=_("My Schedule"), application_icon="mittschema",
            version=__version__, developer_name="Daniel Nylander", website="https://www.autismappar.se",
            license_type=Gtk.License.GPL_3_0, developers=["Daniel Nylander"],
            copyright="\u00a9 2026 Daniel Nylander")
        d.present(self.props.active_window)

    def _on_export(self, *_):
        w = self.props.active_window
        if w: w.do_export()


class ScheduleWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs, default_width=800, default_height=650, title=_("My Schedule"))
        self.schedule = _load_schedule()
        self._build_ui()

    def _build_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(box)
        header = Adw.HeaderBar()
        box.append(header)

        menu = Gio.Menu()
        menu.append(_("Export"), "app.export")
        menu.append(_("About My Schedule"), "app.about")
        menu.append(_("Quit"), "app.quit")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu))

        theme_btn = Gtk.Button(icon_name="weather-clear-night-symbolic",
                               tooltip_text=_("Toggle dark/light theme"))
        theme_btn.connect("clicked", self._toggle_theme)
        header.pack_end(theme_btn)

        # Week grid
        scroll = Gtk.ScrolledWindow(vexpand=True)
        grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=False,
                         row_spacing=4, column_spacing=4)
        grid.set_margin_start(8)
        grid.set_margin_end(8)
        grid.set_margin_top(8)

        # Headers
        for col, day in enumerate(DAYS):
            lbl = Gtk.Label(label=day)
            lbl.add_css_class("title-4")
            grid.attach(lbl, col + 1, 0, 1, 1)

        for row, period in enumerate(PERIODS):
            lbl = Gtk.Label(label=period)
            lbl.add_css_class("title-4")
            grid.attach(lbl, 0, row + 1, 1, 1)

            for col in range(7):
                cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                cell.add_css_class("card")
                cell.set_size_request(90, 80)

                key_d = str(col)
                key_p = str(row)
                activities = self.schedule.get(key_d, {}).get(key_p, [])

                for act in activities:
                    act_label = Gtk.Label(label=f'{act.get("emoji", "")} {act.get("name", "")}')
                    act_label.set_wrap(True)
                    cell.append(act_label)

                add_btn = Gtk.Button(icon_name="list-add-symbolic")
                add_btn.add_css_class("flat")
                add_btn.connect("clicked", self._on_add_activity, col, row)
                cell.append(add_btn)

                grid.attach(cell, col + 1, row + 1, 1, 1)

        scroll.set_child(grid)
        box.append(scroll)

        self.status_label = Gtk.Label(label="", xalign=0)
        self.status_label.add_css_class("dim-label")
        self.status_label.set_margin_start(12)
        self.status_label.set_margin_bottom(4)
        box.append(self.status_label)
        GLib.timeout_add_seconds(1, self._update_clock)

    def _on_add_activity(self, btn, day, period):
        d = Adw.MessageDialog(transient_for=self, heading=_("Add Activity"))
        d.set_body(_("Choose an activity:"))

        flow = Gtk.FlowBox(max_children_per_line=3, selection_mode=Gtk.SelectionMode.SINGLE,
                            homogeneous=True, row_spacing=4, column_spacing=4)
        for act in DEFAULT_ACTIVITIES:
            lbl = Gtk.Label(label=f'{act["emoji"]} {act["name"]}')
            flow.append(lbl)
        d.set_extra_child(flow)
        d.add_response("cancel", _("Cancel"))
        d.add_response("add", _("Add"))
        d.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        def on_resp(dlg, resp):
            if resp == "add":
                sel = flow.get_selected_children()
                if sel:
                    idx = sel[0].get_index()
                    act = DEFAULT_ACTIVITIES[idx]
                    key_d = str(day)
                    key_p = str(period)
                    if key_d not in self.schedule:
                        self.schedule[key_d] = {}
                    if key_p not in self.schedule[key_d]:
                        self.schedule[key_d][key_p] = []
                    self.schedule[key_d][key_p].append(dict(act))
                    _save_schedule(self.schedule)
                    # Rebuild UI
                    self._build_ui()
        d.connect("response", on_resp)
        d.present()

    def do_export(self):
        from mittschema.export import export_csv, export_json
        os.makedirs(CONFIG_DIR, exist_ok=True)
        ts = GLib.DateTime.new_now_local().format("%Y%m%d_%H%M%S")
        data = []
        for d in range(7):
            for p in range(3):
                acts = self.schedule.get(str(d), {}).get(str(p), [])
                for a in acts:
                    data.append({"date": DAYS[d], "details": f'{PERIODS[p]}: {a.get("name", "")}', "result": ""})
        export_csv(data, os.path.join(CONFIG_DIR, f"export_{ts}.csv"))
        export_json(data, os.path.join(CONFIG_DIR, f"export_{ts}.json"))

    def _toggle_theme(self, *_):
        mgr = Adw.StyleManager.get_default()
        mgr.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT if mgr.get_dark() else Adw.ColorScheme.FORCE_DARK)

    def _update_clock(self):
        self.status_label.set_label(GLib.DateTime.new_now_local().format("%Y-%m-%d %H:%M:%S"))
        return True


def main():
    app = ScheduleApp()
    app.run(sys.argv)

if __name__ == "__main__":
    main()

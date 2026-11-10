#!/usr/bin/python3
from ctypes import CDLL
CDLL('libgtk4-layer-shell.so')
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, Gio, GLib, Gtk4LayerShell, Pango, PangoCairo
import calendar
import datetime
import html
import json
import math
import os
import re
import signal
import subprocess
import sys
import threading
import tomllib

# Import shared helpers and sync from popup.py
from popup import (
    _get_credentials,
    _run_sync,
    load_theme,
    hex_to_rgb_float,
    hex_to_rgba,
    load_data,
    load_events,
    NERD_FONT,
    SCOPES,
    CACHE_FILE,
    CREDENTIALS_FILE,
    TOKEN_FILE,
)

BG_PID_FILE = os.path.expanduser('~/.cache/waybar-ycal/bg.pid')
SYNC_INTERVAL_SEC = 15 * 60  # 15 minutes
CURRENT_THEME_FILE = os.path.expanduser('~/.config/waybar-ycal/current_theme.json')
CONFIG_FILE = os.path.expanduser('~/.config/waybar-ycal/config.json')

DEFAULT_CONFIG = {
    "calendar_width": 680,
    "calendar_today_split": "50/50",
    "task_panels_fill_rest": True,
    "task_panel_min_width": 260,
}

DEFAULT_THEME = {
    "name": "dark-pastel-grey-green",
    "display_name": "Dark Pastel Grey-Green",
    "desktop_bg": "linear-gradient(135deg, rgba(22, 27, 25, 0.94), rgba(18, 22, 20, 0.94))",
    "desktop_border": "rgba(255, 255, 255, 0.08)",
    "card_bg": "rgba(33, 40, 37, 0.90)",
    "card_border": "rgba(255, 255, 255, 0.06)",
    "dialog_bg": "rgba(28, 34, 31, 0.98)",
    "text_fg": "#d8deda",
    "text_muted": "rgba(216, 222, 218, 0.5)",
    "accent": "#94baa6",
    "today_bg": "#44544d",
    "today_fg": "#e8efe9",
    "today_border": "rgba(148, 186, 166, 0.35)",
    "save_btn_bg": "#44544d",
    "save_btn_hover": "#50635b",
    "column_themes": [
        {
            "name": "sage",
            "color": "#94baa6",
            "grad": "linear-gradient(90deg, #94baa6, #6b8f7d)",
            "bg_card": "rgba(33, 40, 37, 0.90)",
            "border": "rgba(148, 186, 166, 0.35)",
            "badge_bg": "rgba(148, 186, 166, 0.16)",
        },
        {
            "name": "peach",
            "color": "#caa08c",
            "grad": "linear-gradient(90deg, #caa08c, #a87e6b)",
            "bg_card": "rgba(33, 40, 37, 0.90)",
            "border": "rgba(202, 160, 140, 0.35)",
            "badge_bg": "rgba(202, 160, 140, 0.16)",
        },
        {
            "name": "linen",
            "color": "#cfb989",
            "grad": "linear-gradient(90deg, #cfb989, #ad9868)",
            "bg_card": "rgba(33, 40, 37, 0.90)",
            "border": "rgba(207, 185, 137, 0.35)",
            "badge_bg": "rgba(207, 185, 137, 0.16)",
        },
        {
            "name": "celadon",
            "color": "#86b3a8",
            "grad": "linear-gradient(90deg, #86b3a8, #659187)",
            "bg_card": "rgba(33, 40, 37, 0.90)",
            "border": "rgba(134, 179, 168, 0.35)",
            "badge_bg": "rgba(134, 179, 168, 0.16)",
        },
        {
            "name": "rose",
            "color": "#c97f88",
            "grad": "linear-gradient(90deg, #c97f88, #a85f68)",
            "bg_card": "rgba(33, 40, 37, 0.90)",
            "border": "rgba(201, 127, 136, 0.35)",
            "badge_bg": "rgba(201, 127, 136, 0.16)",
        },
        {
            "name": "slate",
            "color": "#82a4b8",
            "grad": "linear-gradient(90deg, #82a4b8, #638396)",
            "bg_card": "rgba(33, 40, 37, 0.90)",
            "border": "rgba(130, 164, 184, 0.35)",
            "badge_bg": "rgba(130, 164, 184, 0.16)",
        },
        {
            "name": "denim",
            "color": "#8ea0b5",
            "grad": "linear-gradient(90deg, #8ea0b5, #6c7f94)",
            "bg_card": "rgba(33, 40, 37, 0.90)",
            "border": "rgba(142, 160, 181, 0.35)",
            "badge_bg": "rgba(142, 160, 181, 0.16)",
        },
    ]
}


def load_theme():
    if os.path.exists(CURRENT_THEME_FILE):
        try:
            with open(CURRENT_THEME_FILE, 'r') as f:
                data = json.load(f)
                return {**DEFAULT_THEME, **data}
        except Exception as e:
            print(f"[load_theme error] {e}", file=sys.stderr)
    return DEFAULT_THEME


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                content = f.read()
                lines = [l for l in content.splitlines() if not l.strip().startswith(('//', '#'))]
                data = json.loads('\n'.join(lines))
                cfg.update(data)
        except Exception as e:
            print(f"[load_config error] {e}", file=sys.stderr)
    return cfg


def parse_width_setting(val, default=680, total_width=1920):
    if val is None:
        return default
    if isinstance(val, (int, float)):
        if 0 < val <= 1.0:
            return max(300, int(total_width * val))
        return max(300, int(val))
    if isinstance(val, str):
        val = val.strip().lower()
        if val in ('2/3', '2/3 width', 'red line'):
            return 680
        if val in ('standard', 'default'):
            return 680
        if val.endswith('%'):
            try:
                pct = float(val[:-1]) / 100.0
                return max(300, int(total_width * pct))
            except ValueError:
                pass
        if '/' in val:
            try:
                num, den = val.split('/', 1)
                ratio = float(num.strip()) / float(den.strip())
                if 0 < ratio <= 1.0:
                    return max(300, int(total_width * ratio))
                return max(300, int(ratio))
            except Exception:
                pass
        try:
            return max(300, int(val))
        except ValueError:
            pass
    return default


class DesktopBackgroundWindow(Gtk.ApplicationWindow):
    def __init__(self, app, monitor):
        super().__init__(application=app)
        self.app = app
        self.monitor = monitor
        self.today = datetime.date.today()
        self.year = self.today.year
        self.month = self.today.month
        self.selected_date = self.today
        self.events, self.task_lists = load_data()
        self.current_theme = load_theme()
        self.config = load_config()
        self.cal_width = self._calc_calendar_width()

        self._selected_btn = None
        self._collapsed_parents = set()
        self._dialog_mode = 'create'
        self._dialog_task = None
        self._dialog_lists = []
        self._dialog_parent_ids = []
        self._refresh_angle = 0.0
        self._refresh_spin_timer = None

        self._setup_window()
        self._apply_css()
        self._build_ui()

    def _calc_calendar_width(self):
        val = self.config.get('calendar_width', 680)
        total_w = 1920
        if self.monitor:
            try:
                geom = self.monitor.get_geometry()
                if geom and geom.width > 0:
                    total_w = geom.width
            except Exception:
                pass
        return parse_width_setting(val, default=680, total_width=total_w)

    def _setup_window(self):
        self.set_decorated(False)

        Gtk4LayerShell.init_for_window(self)
        Gtk4LayerShell.set_layer(self, Gtk4LayerShell.Layer.BOTTOM)
        if self.monitor:
            Gtk4LayerShell.set_monitor(self, self.monitor)

        for edge in [Gtk4LayerShell.Edge.TOP, Gtk4LayerShell.Edge.BOTTOM,
                     Gtk4LayerShell.Edge.LEFT, Gtk4LayerShell.Edge.RIGHT]:
            Gtk4LayerShell.set_anchor(self, edge, True)

        # Margin: Waybar is at top (height 31px), leave 36px top margin
        Gtk4LayerShell.set_margin(self, Gtk4LayerShell.Edge.TOP, 36)
        Gtk4LayerShell.set_margin(self, Gtk4LayerShell.Edge.BOTTOM, 10)
        Gtk4LayerShell.set_margin(self, Gtk4LayerShell.Edge.LEFT, 12)
        Gtk4LayerShell.set_margin(self, Gtk4LayerShell.Edge.RIGHT, 12)

        Gtk4LayerShell.set_exclusive_zone(self, -1)
        Gtk4LayerShell.set_keyboard_mode(self, Gtk4LayerShell.KeyboardMode.ON_DEMAND)

        # Escape closes dialog if open
        key_ctrl = Gtk.EventControllerKey()
        def on_key(ctrl, keyval, keycode, state):
            if keyval == 65307:  # Escape
                if hasattr(self, 'dialog_scrim') and self.dialog_scrim.get_visible():
                    self.close_task_dialog()
                    return True
            return False
        key_ctrl.connect("key-pressed", on_key)
        self.add_controller(key_ctrl)

    def _build_ui(self):
        self.root_overlay = Gtk.Overlay()
        self.root_overlay.set_hexpand(True)
        self.root_overlay.set_vexpand(True)
        self.set_child(self.root_overlay)

        # Main background container
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.set_hexpand(True)
        self.main_box.set_vexpand(True)
        self.main_box.add_css_class('desktop-bg')
        self.root_overlay.set_child(self.main_box)

        # ── 1. Top Header Bar ─────────────────────────────────────────
        self._build_header_bar()

        # ── 2. Content Row: Left (Calendar + Agenda), Right (Task Boards)
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        content_box.set_vexpand(True)
        content_box.set_hexpand(True)
        self.main_box.append(content_box)

        # ── Left Column: Calendar & Agenda (50/50 vertical split, width 680px at red line) ──
        self.left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.left_col.set_homogeneous(True)
        self.left_col.set_size_request(self.cal_width, -1)
        self.left_col.set_hexpand(False)
        content_box.append(self.left_col)

        self._build_calendar_card()
        self._build_agenda_card()

        # ── Right Column: Kanban Task Boards (Vibrant colors) ──────────
        self._build_task_boards(content_box)

        # ── Modal Task Creation/Edit Dialog ───────────────────────────
        self._build_task_dialog()

    def _build_header_bar(self):
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hdr.add_css_class('desktop-card')
        hdr.add_css_class('desktop-header-card')
        hdr.set_size_request(-1, 50)
        self.main_box.append(hdr)

        # Date & Live Clock
        date_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        date_box.set_valign(Gtk.Align.CENTER)

        self.date_lbl = Gtk.Label()
        self.date_lbl.add_css_class('header-date')

        self.clock_lbl = Gtk.Label()
        self.clock_lbl.add_css_class('header-clock')

        date_box.append(self.date_lbl)
        date_box.append(self.clock_lbl)
        hdr.append(date_box)
        self._update_clock()

        # Center Overview Status Pills
        stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        stats_box.set_hexpand(True)
        stats_box.set_halign(Gtk.Align.CENTER)
        stats_box.set_valign(Gtk.Align.CENTER)

        self.due_pill = Gtk.Label()
        self.due_pill.add_css_class('status-pill')
        self.due_pill.add_css_class('pill-due')

        self.pending_pill = Gtk.Label()
        self.pending_pill.add_css_class('status-pill')
        self.pending_pill.add_css_class('pill-pending')

        self.lists_pill = Gtk.Label()
        self.lists_pill.add_css_class('status-pill')
        self.lists_pill.add_css_class('pill-lists')

        stats_box.append(self.due_pill)
        stats_box.append(self.pending_pill)
        stats_box.append(self.lists_pill)
        hdr.append(stats_box)

        # Right Action Buttons
        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        actions_box.set_valign(Gtk.Align.CENTER)

        new_task_btn = Gtk.Button(label="+ New Task")
        new_task_btn.add_css_class('action-btn-primary')
        new_task_btn.set_tooltip_text("Create a new task with full options")
        new_task_btn.connect("clicked", lambda *_: self.open_task_dialog(mode='create'))

        new_ev_btn = Gtk.Button(label="+ Event")
        new_ev_btn.add_css_class('action-btn')
        new_ev_btn.set_tooltip_text("Create event in Google Calendar")
        new_ev_btn.connect("clicked", lambda *_: subprocess.Popen(['xdg-open', 'https://calendar.google.com/calendar/r/eventedit']))

        self._refresh_da = Gtk.DrawingArea()
        self._refresh_da.set_size_request(20, 20)
        self._refresh_da.set_draw_func(self._draw_refresh_icon)

        self.refresh_btn = Gtk.Button()
        self.refresh_btn.set_child(self._refresh_da)
        self.refresh_btn.set_size_request(30, 30)
        self.refresh_btn.add_css_class('action-btn')
        self.refresh_btn.set_tooltip_text("Sync Google Calendar & Tasks")
        self.refresh_btn.connect("clicked", self._on_refresh_clicked)

        open_tasks_btn = Gtk.Button(label="↗ Tasks Web")
        open_tasks_btn.add_css_class('action-btn')
        open_tasks_btn.connect("clicked", lambda *_: subprocess.Popen(['xdg-open', 'https://calendar.google.com/calendar/u/0/r/tasks']))

        actions_box.append(new_task_btn)
        actions_box.append(new_ev_btn)
        actions_box.append(self.refresh_btn)
        actions_box.append(open_tasks_btn)
        hdr.append(actions_box)

        self._update_stats_pills()

    def _update_clock(self):
        now = datetime.datetime.now()
        weekday_str = now.strftime('%A')
        date_str = now.strftime('%d %B %Y')
        self.date_lbl.set_markup(f"<b>{weekday_str}</b>  <span alpha='65%'>{date_str}</span>")
        self.clock_lbl.set_markup(f"<b>{now.strftime('%H:%M:%S')}</b>")
        return True

    def _update_stats_pills(self):
        today_iso = datetime.date.today().isoformat()
        today_items = self.events.get(today_iso, [])
        due_today_tasks = sum(1 for item in today_items if isinstance(item, dict) and not item.get('done'))

        total_pending = 0
        for tl in self.task_lists:
            def count_p(tasks):
                c = 0
                for t in tasks:
                    if not t.get('done'):
                        c += 1
                    c += count_p(t.get('subtasks', []))
                return c
            total_pending += count_p(tl.get('tasks', []))

        lists_count = len(self.task_lists)

        self.due_pill.set_markup(f"<b>📌 {due_today_tasks}</b> Due Today")
        self.pending_pill.set_markup(f"<b>📋 {total_pending}</b> Pending")
        self.lists_pill.set_markup(f"<b>📁 {lists_count}</b> Lists")

    def _build_calendar_card(self):
        self.calendar_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.calendar_card.add_css_class('desktop-card')
        self.calendar_card.add_css_class('calendar-card')
        self.calendar_card.set_vexpand(True)
        self.left_col.append(self.calendar_card)

        # Header: Prev, Month Label, Next, Today button
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        prev_btn = Gtk.Button(label="‹")
        prev_btn.add_css_class('nav-btn')
        prev_btn.connect("clicked", lambda _: self._navigate(-1))

        self.month_label = Gtk.Label()
        self.month_label.set_markup(
            f"<b>{datetime.date(self.year, self.month, 1).strftime('%B %Y').upper()}</b>"
        )
        self.month_label.set_hexpand(True)
        self.month_label.add_css_class('calendar-title')

        next_btn = Gtk.Button(label="›")
        next_btn.add_css_class('nav-btn')
        next_btn.connect("clicked", lambda _: self._navigate(1))

        today_btn = Gtk.Button(label="Today")
        today_btn.add_css_class('pill-btn')
        today_btn.connect("clicked", self._on_today_clicked)

        hdr.append(prev_btn)
        hdr.append(self.month_label)
        hdr.append(next_btn)
        hdr.append(today_btn)
        self.calendar_card.append(hdr)

        self.grid_container = Gtk.Box()
        self.grid_container.set_vexpand(True)
        self.grid_container.set_hexpand(True)
        self.calendar_card.append(self.grid_container)
        self._build_grid()

    def _build_grid(self):
        while True:
            child = self.grid_container.get_first_child()
            if child is None:
                break
            self.grid_container.remove(child)

        self._selected_btn = None
        grid = Gtk.Grid()
        grid.set_row_spacing(4)
        grid.set_column_spacing(4)
        grid.set_column_homogeneous(True)
        grid.set_row_homogeneous(True)
        grid.set_hexpand(True)
        grid.set_vexpand(True)

        day_names = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for col, name in enumerate(day_names):
            lbl = Gtk.Label(label=name)
            lbl.add_css_class('weekday')
            if col >= 5:
                lbl.add_css_class('weekend-label')
            lbl.set_hexpand(True)
            grid.attach(lbl, col, 0, 1, 1)

        first = datetime.date(self.year, self.month, 1)
        start = first - datetime.timedelta(days=first.weekday())
        last = datetime.date(self.year, self.month, calendar.monthrange(self.year, self.month)[1])
        weeks = math.ceil((first.weekday() + last.day) / 7)
        total_days = weeks * 7

        for i in range(total_days):
            date = start + datetime.timedelta(days=i)
            day_events = self.events.get(date.isoformat(), [])

            overlay = Gtk.Overlay()
            overlay.set_hexpand(True)
            overlay.set_vexpand(True)

            number = Gtk.Label(label=str(date.day))
            number.add_css_class('day-number')
            number.set_halign(Gtk.Align.CENTER)
            number.set_valign(Gtk.Align.CENTER)
            overlay.set_child(number)

            has_events = any(isinstance(e, str) for e in day_events)
            has_tasks = any(isinstance(e, dict) and not e.get('done') for e in day_events)

            if has_events or has_tasks:
                bar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
                bar_box.set_halign(Gtk.Align.CENTER)
                bar_box.set_valign(Gtk.Align.END)
                bar_box.set_margin_bottom(4)
                w = 12 if (has_events and has_tasks) else 20
                if has_tasks:
                    task_bar = Gtk.Box()
                    task_bar.add_css_class('task-bar')
                    task_bar.set_size_request(w, 3)
                    bar_box.append(task_bar)
                if has_events:
                    bar = Gtk.Box()
                    bar.add_css_class('event-bar')
                    bar.set_size_request(w, 3)
                    bar_box.append(bar)
                overlay.add_overlay(bar_box)

            btn = Gtk.Button()
            btn.set_child(overlay)
            btn.set_hexpand(True)
            btn.set_vexpand(True)
            btn.date = date
            btn.connect("clicked", self._on_day_clicked)
            btn.add_css_class("calendar-day-btn")

            if date.month != self.month:
                btn.add_css_class("other-month")
            if date.weekday() >= 5:
                btn.add_css_class("weekend")
            if date == self.today:
                btn.add_css_class("today")
            if date == self.selected_date:
                btn.add_css_class("selected")
                self._selected_btn = btn

            row = i // 7 + 1
            col = i % 7
            grid.attach(btn, col, row, 1, 1)

        self.grid_container.append(grid)

    def _on_day_clicked(self, btn):
        if self._selected_btn is not None:
            self._selected_btn.remove_css_class('selected')
        self._selected_btn = btn
        btn.add_css_class('selected')
        self.selected_date = btn.date
        self._update_agenda_card(btn.date)

    def _on_today_clicked(self, _):
        self.year = self.today.year
        self.month = self.today.month
        self.selected_date = self.today
        self.month_label.set_markup(
            f"<b>{datetime.date(self.year, self.month, 1).strftime('%B %Y').upper()}</b>"
        )
        self._build_grid()
        self._update_agenda_card(self.today)

    def _build_agenda_card(self):
        self.agenda_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.agenda_card.add_css_class('desktop-card')
        self.agenda_card.add_css_class('agenda-card')
        self.agenda_card.set_vexpand(True)
        self.left_col.append(self.agenda_card)

        self.agenda_hdr = Gtk.Label()
        self.agenda_hdr.set_halign(Gtk.Align.START)
        self.agenda_hdr.add_css_class('agenda-heading')
        self.agenda_card.append(self.agenda_hdr)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        self.agenda_card.append(scroll)

        self.agenda_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        scroll.set_child(self.agenda_box)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_row.set_size_request(-1, 30)

        add_task_day_btn = Gtk.Button(label="+ Task for Today")
        add_task_day_btn.add_css_class('add-btn')
        add_task_day_btn.set_hexpand(True)
        add_task_day_btn.connect(
            "clicked",
            lambda *_: self.open_task_dialog(mode='create', default_date=self.selected_date)
        )

        open_day_cal_btn = Gtk.Button()
        cal_icon = Gtk.Label(label="\uf073")
        cal_icon.add_css_class('nerd')
        open_day_cal_btn.set_child(cal_icon)
        open_day_cal_btn.set_size_request(28, -1)
        open_day_cal_btn.add_css_class('add-btn')
        open_day_cal_btn.set_tooltip_text("Open day in Google Calendar")
        open_day_cal_btn.connect("clicked", self._on_open_day_cal_clicked)

        btn_row.append(add_task_day_btn)
        btn_row.append(open_day_cal_btn)
        self.agenda_card.append(btn_row)

        self._update_agenda_card(self.today)

    def _update_agenda_card(self, date):
        if date == self.today:
            heading = f"<b>Today</b>  <span alpha='65%'>{date.strftime('%a, %d %b')}</span>"
        else:
            heading = f"<b>{date.strftime('%a')}</b>  <span alpha='65%'>{date.strftime('%d %b %Y')}</span>"
        self.agenda_hdr.set_markup(heading)

        while True:
            child = self.agenda_box.get_first_child()
            if child is None:
                break
            self.agenda_box.remove(child)

        day_events = sorted(
            self.events.get(date.isoformat(), []),
            key=lambda e: 0 if (isinstance(e, dict) and not e.get('done')) else (1 if isinstance(e, dict) else 2)
        )

        if day_events:
            for ev in day_events:
                self.agenda_box.append(self._make_agenda_row(ev))
        else:
            empty = Gtk.Label(label="No events or tasks scheduled")
            empty.add_css_class('no-events')
            empty.set_halign(Gtk.Align.START)
            self.agenda_box.append(empty)

    def _make_agenda_row(self, ev):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.add_css_class('agenda-row')

        if isinstance(ev, dict):
            done = ev.get('done', False)
            is_sub = bool(ev.get('parent'))

            if is_sub:
                glyph = Gtk.Label(label="↳")
                glyph.add_css_class('subtask-glyph')
                row.append(glyph)

            dot = Gtk.Label(label="•")
            dot.add_css_class('done-dot' if done else 'task-dot')
            row.append(dot)

            title_btn = Gtk.Button()
            title_btn.add_css_class('task-title-btn')
            title_btn.set_hexpand(True)
            title_btn.connect("clicked", lambda *_: self.open_task_dialog(mode='edit', task=ev))

            label = Gtk.Label()
            label.set_halign(Gtk.Align.START)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.add_css_class('event-name')

            title = ev.get('title', '(no title)')
            time_part = f"<span alpha='75%' size='small'>{ev['time']}</span>  " if ev.get('time') else ""
            notes_icon = " <span alpha='50%' size='small'>\uf249</span>" if ev.get('notes') else ""

            if done:
                label.set_markup(f"{time_part}<span alpha='50%'><s>{html.escape(title)}</s></span>{notes_icon}")
            else:
                label.set_markup(f"{time_part}{html.escape(title)}{notes_icon}")

            title_btn.set_child(label)
            row.append(title_btn)

            tooltip_lines = [title]
            if ev.get('time'):
                tooltip_lines.append(f"Time: {ev['time']}")
            if is_sub and ev.get('parent_title'):
                tooltip_lines.append(f"Parent: {ev['parent_title']}")
            if ev.get('notes'):
                tooltip_lines.append(f"Notes:\n{ev['notes']}")
            row.set_tooltip_text("\n".join(tooltip_lines))

            toggle = Gtk.Button(label="✓")
            toggle.add_css_class('done-toggle')
            toggle.add_css_class('done-toggle-active' if done else 'done-toggle-inactive')
            toggle.connect("clicked", self._on_task_toggle, ev)
            row.append(toggle)
        else:
            dot = Gtk.Label(label="•")
            dot.add_css_class('event-dot')
            name = Gtk.Label(label=ev)
            name.set_ellipsize(Pango.EllipsizeMode.END)
            name.set_tooltip_text(ev)
            name.add_css_class('event-name')
            row.append(dot)
            row.append(name)

        return row

    def _on_open_day_cal_clicked(self, _):
        d = self.selected_date
        url = f"https://calendar.google.com/calendar/r/day/{d.year}/{d.month}/{d.day}"
        subprocess.Popen(['xdg-open', url])

    def _build_task_boards(self, parent_box):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        parent_box.append(scroll)

        fill_rest = self.config.get('task_panels_fill_rest', True)
        self.boards_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.boards_box.set_hexpand(True)
        self.boards_box.set_vexpand(True)
        if fill_rest:
            self.boards_box.set_homogeneous(True)
        scroll.set_child(self.boards_box)

        self._populate_task_boards()

    def _populate_task_boards(self):
        while True:
            child = self.boards_box.get_first_child()
            if child is None:
                break
            self.boards_box.remove(child)

        if not self.task_lists:
            empty = Gtk.Label(label="No Google Tasks lists found. Syncing...")
            empty.add_css_class('no-events')
            self.boards_box.append(empty)
            return

        min_w = self.config.get('task_panel_min_width', 260)
        fill_rest = self.config.get('task_panels_fill_rest', True)

        col_themes = self.current_theme.get('column_themes') or DEFAULT_THEME['column_themes']
        for idx, tl in enumerate(self.task_lists):
            theme = col_themes[idx % len(col_themes)]

            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            col.set_size_request(min_w, -1)
            if fill_rest:
                col.set_hexpand(True)
            col.set_vexpand(True)
            col.add_css_class('desktop-card')
            col.add_css_class('kanban-column')
            col.add_css_class(f"kanban-theme-{theme['name']}")
            self.boards_box.append(col)

            # Top colored accent line
            accent_bar = Gtk.Box()
            accent_bar.add_css_class('kanban-top-bar')
            accent_bar.add_css_class(f"accent-bg-{theme['name']}")
            accent_bar.set_size_request(-1, 3)
            col.append(accent_bar)

            tl_tasks = tl.get('tasks', [])

            def count_p(tasks):
                c = 0
                for t in tasks:
                    if not t.get('done'):
                        c += 1
                    c += count_p(t.get('subtasks', []))
                return c

            pending_count = count_p(tl_tasks)

            # Column Header
            hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            title_lbl = Gtk.Label()
            title_lbl.set_markup(
                f"<span weight='bold' foreground='{theme['color']}'>{html.escape(tl.get('title', 'Tasks'))}</span>"
            )
            title_lbl.set_halign(Gtk.Align.START)
            title_lbl.set_hexpand(True)
            title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            title_lbl.set_tooltip_text(tl.get('title', 'Tasks'))
            title_lbl.add_css_class('kanban-title')
            hdr.append(title_lbl)

            count_badge = Gtk.Label(label=str(pending_count))
            count_badge.add_css_class('kanban-count-badge')
            count_badge.add_css_class(f"badge-{theme['name']}")
            hdr.append(count_badge)

            add_icon_btn = Gtk.Button(label="+")
            add_icon_btn.add_css_class('theme-add-btn')
            add_icon_btn.add_css_class(f"btn-{theme['name']}")
            add_icon_btn.set_tooltip_text(f"Add task to {tl.get('title', '')}")
            add_icon_btn.connect("clicked", lambda _, lid=tl['id']: self.open_task_dialog(mode='create', default_list_id=lid))
            hdr.append(add_icon_btn)

            col.append(hdr)

            # Scrolled Tasks Area
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.set_vexpand(True)
            col.append(scroll)

            tasks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            scroll.set_child(tasks_box)

            sorted_tasks = sorted(
                tl_tasks,
                key=lambda t: (1 if t.get('done') else 0, t.get('due') or '9999-99-99')
            )

            if sorted_tasks:
                for task in sorted_tasks:
                    tasks_box.append(self._make_task_item_row(task, is_subtask=False, theme=theme))
            else:
                empty = Gtk.Label(label="No tasks in this list")
                empty.add_css_class('no-events')
                empty.set_halign(Gtk.Align.START)
                tasks_box.append(empty)

            # Column Footer
            col.append(self._make_column_footer(tl, theme))

    def _make_task_item_row(self, task, is_subtask=False, theme=None):
        done = task.get('done', False)
        subtasks = task.get('subtasks', [])
        has_subtasks = bool(subtasks) and not is_subtask

        item_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        item_row.add_css_class('task-item-card')

        if is_subtask:
            item_row.set_margin_start(16)
            glyph = Gtk.Label()
            glyph_color = theme['color'] if theme else '#38bdf8'
            glyph.set_markup(f"<span color='{glyph_color}'>↳</span>")
            glyph.add_css_class('subtask-glyph')
            item_row.append(glyph)

        dot = Gtk.Label(label="•")
        dot.add_css_class('done-dot' if done else 'task-dot')
        item_row.append(dot)

        # Subtasks toggle button
        subtasks_container = None
        if has_subtasks:
            is_collapsed = task['id'] in self._collapsed_parents
            subs_done = sum(1 for s in subtasks if s.get('done'))
            toggle_lbl = Gtk.Label(label=f"{'▶' if is_collapsed else '▼'} {subs_done}/{len(subtasks)}")
            toggle_lbl.add_css_class('subtask-badge')
            if theme:
                toggle_lbl.add_css_class(f"badge-{theme['name']}")

            toggle_btn = Gtk.Button()
            toggle_btn.set_child(toggle_lbl)
            toggle_btn.add_css_class('subtasks-toggle-btn')
            toggle_btn.set_tooltip_text(f"{subs_done}/{len(subtasks)} subtasks done. Click to toggle expand.")

            def on_toggle_subs(_):
                if task['id'] in self._collapsed_parents:
                    self._collapsed_parents.remove(task['id'])
                    toggle_lbl.set_label(f"▼ {subs_done}/{len(subtasks)}")
                    if subtasks_container:
                        subtasks_container.set_visible(True)
                else:
                    self._collapsed_parents.add(task['id'])
                    toggle_lbl.set_label(f"▶ {subs_done}/{len(subtasks)}")
                    if subtasks_container:
                        subtasks_container.set_visible(False)
            toggle_btn.connect("clicked", on_toggle_subs)
            item_row.append(toggle_btn)

        # Title button
        title_btn = Gtk.Button()
        title_btn.add_css_class('task-title-btn')
        title_btn.set_hexpand(True)
        title_btn.connect("clicked", lambda *_: self.open_task_dialog(mode='edit', task=task))

        name_lbl = Gtk.Label()
        name_lbl.set_halign(Gtk.Align.START)
        name_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        name_lbl.add_css_class('event-name')

        title = task.get('title', '(no title)')
        due = task.get('due')
        due_time = task.get('time')

        due_badge = ""
        if due:
            try:
                d_obj = datetime.date.fromisoformat(due)
                today = datetime.date.today()
                time_str = f" {due_time}" if due_time else ""
                if d_obj == today:
                    due_badge = f"<span foreground='#caa08c' size='small'>Today{time_str}</span>"
                elif d_obj < today and not done:
                    due_badge = f"<span foreground='#c97f88' weight='bold' size='small'>{d_obj.strftime('%d %b')}{time_str}</span>"
                else:
                    due_badge = f"<span foreground='#94baa6' size='small'>{d_obj.strftime('%d %b')}{time_str}</span>"
            except Exception:
                due_badge = ""

        notes_icon = " <span alpha='55%' size='small'>\uf249</span>" if task.get('notes') else ""

        if done:
            name_lbl.set_markup(f"<span alpha='50%'><s>{html.escape(title)}</s></span>{notes_icon}")
        else:
            if due_badge:
                name_lbl.set_markup(f"{html.escape(title)}  {due_badge}{notes_icon}")
            else:
                name_lbl.set_markup(f"{html.escape(title)}{notes_icon}")

        title_btn.set_child(name_lbl)
        item_row.append(title_btn)

        tooltip_parts = [title]
        if due:
            t_str = f" {due_time}" if due_time else ""
            tooltip_parts.append(f"Due: {due}{t_str}")
        if is_subtask and task.get('parent_title'):
            tooltip_parts.append(f"Parent: {task['parent_title']}")
        if task.get('notes'):
            tooltip_parts.append(f"Notes:\n{task['notes']}")
        if has_subtasks:
            subs_done = sum(1 for s in subtasks if s.get('done'))
            tooltip_parts.append(f"Subtasks: {subs_done}/{len(subtasks)} done")
        item_row.set_tooltip_text("\n".join(tooltip_parts))

        # Add subtask button on parent tasks
        if not is_subtask:
            add_sub_btn = Gtk.Button()
            add_sub_lbl = Gtk.Label()
            col_txt = theme['color'] if theme else '#38bdf8'
            add_sub_lbl.set_markup(f"<span color='{col_txt}'>↳+</span>")
            add_sub_lbl.set_halign(Gtk.Align.CENTER)
            add_sub_lbl.set_valign(Gtk.Align.CENTER)
            add_sub_btn.set_child(add_sub_lbl)
            add_sub_btn.add_css_class('task-row-btn')
            add_sub_btn.set_tooltip_text("Add subtask")
            add_sub_btn.connect(
                "clicked",
                lambda *_: self.open_task_dialog(
                    mode='create',
                    default_list_id=task['lid'],
                    default_parent_id=task['id']
                )
            )
            item_row.append(add_sub_btn)

        # Edit button
        edit_btn = Gtk.Button()
        edit_lbl = Gtk.Label(label="\uf044")
        edit_lbl.set_halign(Gtk.Align.CENTER)
        edit_lbl.set_valign(Gtk.Align.CENTER)
        edit_btn.set_child(edit_lbl)
        edit_btn.add_css_class('task-row-btn')
        edit_btn.add_css_class('nerd')
        edit_btn.set_tooltip_text("Edit task details")
        edit_btn.connect("clicked", lambda *_: self.open_task_dialog(mode='edit', task=task))
        item_row.append(edit_btn)

        # Done toggle button
        toggle = Gtk.Button(label="✓")
        toggle.add_css_class('done-toggle')
        toggle.add_css_class('done-toggle-active' if done else 'done-toggle-inactive')
        toggle.connect("clicked", self._on_task_toggle, task)
        item_row.append(toggle)

        if not has_subtasks:
            return item_row

        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        container.append(item_row)

        subtasks_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        is_collapsed = task['id'] in self._collapsed_parents
        subtasks_container.set_visible(not is_collapsed)

        sorted_subs = sorted(
            subtasks,
            key=lambda t: (1 if t.get('done') else 0, t.get('due') or '9999-99-99')
        )
        for sub in sorted_subs:
            subtasks_container.append(self._make_task_item_row(sub, is_subtask=True, theme=theme))

        container.append(subtasks_container)
        return container

    def _make_column_footer(self, tl, theme=None):
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_row.set_size_request(-1, 30)

        add_btn = Gtk.Button(label="+ Add")
        add_btn.add_css_class('kanban-footer-btn')
        if theme:
            add_btn.add_css_class(f"footer-btn-{theme['name']}")
        add_btn.set_hexpand(True)
        add_btn.set_tooltip_text("Quick task add (title only)")

        detail_btn = Gtk.Button()
        detail_lbl = Gtk.Label(label="\uf013")
        detail_lbl.set_halign(Gtk.Align.CENTER)
        detail_lbl.set_valign(Gtk.Align.CENTER)
        detail_btn.set_child(detail_lbl)
        detail_btn.set_size_request(28, -1)
        detail_btn.add_css_class('kanban-footer-btn')
        detail_btn.add_css_class('nerd')
        detail_btn.set_tooltip_text("Detailed task options (datetime, notes, subtask)")
        detail_btn.connect("clicked", lambda *_: self.open_task_dialog(mode='create', default_list_id=tl['id']))

        open_btn = Gtk.Button()
        open_lbl = Gtk.Label(label="\uf08e")
        open_lbl.set_halign(Gtk.Align.CENTER)
        open_lbl.set_valign(Gtk.Align.CENTER)
        open_btn.set_child(open_lbl)
        open_btn.set_size_request(28, -1)
        open_btn.add_css_class('kanban-footer-btn')
        open_btn.add_css_class('nerd')
        open_btn.set_tooltip_text("Open Google Tasks in browser")
        open_btn.connect(
            "clicked",
            lambda _: subprocess.Popen(['xdg-open', 'https://calendar.google.com/calendar/u/0/r/tasks'])
        )

        btn_row.append(add_btn)
        btn_row.append(detail_btn)
        btn_row.append(open_btn)
        container.append(btn_row)

        entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        entry_row.set_visible(False)

        entry = Gtk.Entry()
        entry.set_placeholder_text("Task title (Enter to save)...")
        entry.add_css_class('task-entry')
        entry.set_hexpand(True)
        entry_row.append(entry)

        expand_btn = Gtk.Button()
        expand_lbl = Gtk.Label(label="…")
        expand_lbl.set_halign(Gtk.Align.CENTER)
        expand_lbl.set_valign(Gtk.Align.CENTER)
        expand_btn.set_child(expand_lbl)
        expand_btn.set_size_request(28, -1)
        expand_btn.add_css_class('kanban-footer-btn')
        expand_btn.set_tooltip_text("Expand to detailed form")
        entry_row.append(expand_btn)

        container.append(entry_row)

        def on_add_clicked(_):
            btn_row.set_visible(False)
            entry_row.set_visible(True)
            entry.set_text("")
            entry.grab_focus()

        def on_activate(ent):
            val = ent.get_text().strip()
            if val:
                ent.set_sensitive(False)
                self._add_task_to_list(tl['id'], val)
            btn_row.set_visible(True)
            entry_row.set_visible(False)
            entry.set_sensitive(True)

        def on_cancel():
            btn_row.set_visible(True)
            entry_row.set_visible(False)

        def on_expand(_):
            current_text = entry.get_text().strip()
            on_cancel()
            self.open_task_dialog(mode='create', default_list_id=tl['id'])
            if current_text:
                self.dialog_title_entry.set_text(current_text)

        add_btn.connect("clicked", on_add_clicked)
        entry.connect("activate", on_activate)
        expand_btn.connect("clicked", on_expand)

        key_ctrl = Gtk.EventControllerKey()
        def on_key(ctrl, keyval, keycode, state):
            if keyval == 65307:  # Escape key
                on_cancel()
                return True
            return False
        key_ctrl.connect("key-pressed", on_key)
        entry.add_controller(key_ctrl)

        return container

    def _add_task_to_list(self, lid, title):
        def do_add():
            try:
                from googleapiclient.discovery import build
                creds = _get_credentials()
                if creds is None:
                    return
                service = build('tasks', 'v1', credentials=creds)
                service.tasks().insert(tasklist=lid, body={'title': title}).execute()
                _run_sync()
                GLib.idle_add(self.app.reload_all_windows)
            except Exception as e:
                print(f'[add task error] {e}', file=sys.stderr)
        threading.Thread(target=do_add, daemon=True).start()

    def _on_task_toggle(self, btn, task):
        btn.set_sensitive(False)
        btn.add_css_class('pulsing')
        def do_toggle():
            try:
                from googleapiclient.discovery import build
                creds = _get_credentials()
                if creds is None:
                    return
                service = build('tasks', 'v1', credentials=creds)
                new_status = 'needsAction' if task.get('done') else 'completed'
                service.tasks().patch(
                    tasklist=task['lid'],
                    task=task['id'],
                    body={'status': new_status},
                ).execute()
                _run_sync()
                GLib.idle_add(self.app.reload_all_windows)
            except Exception as e:
                print(f'[task toggle error] {e}', file=sys.stderr)
                def after_err():
                    btn.remove_css_class('pulsing')
                    btn.set_sensitive(True)
                    return False
                GLib.idle_add(after_err)
        threading.Thread(target=do_toggle, daemon=True).start()

    # ── Task Creation & Editing Dialog ──────────────────────────────
    def _build_task_dialog(self):
        self.dialog_scrim = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.dialog_scrim.set_hexpand(True)
        self.dialog_scrim.set_vexpand(True)
        self.dialog_scrim.add_css_class('dialog-scrim')
        self.dialog_scrim.set_visible(False)
        self.root_overlay.add_overlay(self.dialog_scrim)

        self.dialog_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.dialog_card.add_css_class('desktop-card')
        self.dialog_card.add_css_class('dialog-card')
        self.dialog_card.set_size_request(380, -1)
        self.dialog_card.set_halign(Gtk.Align.CENTER)
        self.dialog_card.set_valign(Gtk.Align.CENTER)
        self.dialog_scrim.append(self.dialog_card)

        # Header: Title + Close Button
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.dialog_title_lbl = Gtk.Label()
        self.dialog_title_lbl.set_markup("<b>New Task</b>")
        self.dialog_title_lbl.set_halign(Gtk.Align.START)
        self.dialog_title_lbl.set_hexpand(True)
        self.dialog_title_lbl.add_css_class('dialog-title')
        hdr.append(self.dialog_title_lbl)

        close_btn = Gtk.Button(label="✕")
        close_btn.add_css_class('dialog-close-btn')
        close_btn.connect("clicked", lambda *_: self.close_task_dialog())
        hdr.append(close_btn)
        self.dialog_card.append(hdr)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(440)
        scroll.set_propagate_natural_height(True)
        self.dialog_card.append(scroll)

        form_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scroll.set_child(form_box)

        # List selector
        list_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        list_lbl = Gtk.Label(label="List:")
        list_lbl.set_size_request(50, -1)
        list_lbl.set_halign(Gtk.Align.START)
        list_lbl.add_css_class('dialog-label')
        list_row.append(list_lbl)

        self.dialog_list_dropdown = Gtk.DropDown()
        self.dialog_list_dropdown.set_hexpand(True)
        self.dialog_list_dropdown.connect("notify::selected", lambda *_: self._on_dialog_list_changed())
        list_row.append(self.dialog_list_dropdown)
        form_box.append(list_row)

        # Parent task selector (for subtasks)
        parent_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        parent_lbl = Gtk.Label(label="Parent:")
        parent_lbl.set_size_request(50, -1)
        parent_lbl.set_halign(Gtk.Align.START)
        parent_lbl.add_css_class('dialog-label')
        parent_row.append(parent_lbl)

        self.dialog_parent_dropdown = Gtk.DropDown()
        self.dialog_parent_dropdown.set_hexpand(True)
        parent_row.append(self.dialog_parent_dropdown)
        form_box.append(parent_row)

        # Task Title
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_lbl = Gtk.Label(label="Title:")
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.add_css_class('dialog-label')
        title_box.append(title_lbl)

        self.dialog_title_entry = Gtk.Entry()
        self.dialog_title_entry.set_placeholder_text("Task title...")
        self.dialog_title_entry.add_css_class('task-entry')
        self.dialog_title_entry.connect("activate", lambda *_: self._save_task())
        title_box.append(self.dialog_title_entry)
        form_box.append(title_box)

        # Due Date Section
        date_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        date_hdr = Gtk.Label(label="Due Date:")
        date_hdr.set_halign(Gtk.Align.START)
        date_hdr.add_css_class('dialog-label')
        date_box.append(date_hdr)

        date_presets = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_today = Gtk.Button(label="Today")
        btn_today.add_css_class('pill-btn')
        btn_today.connect("clicked", lambda *_: self.dialog_date_entry.set_text(datetime.date.today().isoformat()))

        btn_tmrw = Gtk.Button(label="Tomorrow")
        btn_tmrw.add_css_class('pill-btn')
        btn_tmrw.connect("clicked", lambda *_: self.dialog_date_entry.set_text((datetime.date.today() + datetime.timedelta(days=1)).isoformat()))

        btn_mon = Gtk.Button(label="Next Mon")
        btn_mon.add_css_class('pill-btn')
        def on_next_mon(_):
            t = datetime.date.today()
            d = (0 - t.weekday()) % 7
            if d == 0: d = 7
            self.dialog_date_entry.set_text((t + datetime.timedelta(days=d)).isoformat())
        btn_mon.connect("clicked", on_next_mon)

        btn_clear_d = Gtk.Button(label="Clear")
        btn_clear_d.add_css_class('pill-btn')
        btn_clear_d.connect("clicked", lambda *_: self.dialog_date_entry.set_text(""))

        date_presets.append(btn_today)
        date_presets.append(btn_tmrw)
        date_presets.append(btn_mon)
        date_presets.append(btn_clear_d)
        date_box.append(date_presets)

        self.dialog_date_entry = Gtk.Entry()
        self.dialog_date_entry.set_placeholder_text("YYYY-MM-DD")
        self.dialog_date_entry.add_css_class('task-entry')
        date_box.append(self.dialog_date_entry)
        form_box.append(date_box)

        # Due Time Section
        time_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        time_hdr = Gtk.Label(label="Time (optional):")
        time_hdr.set_halign(Gtk.Align.START)
        time_hdr.add_css_class('dialog-label')
        time_box.append(time_hdr)

        time_presets = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for t_val in ["09:00", "13:00", "17:00", "20:00"]:
            b = Gtk.Button(label=t_val)
            b.add_css_class('pill-btn')
            b.connect("clicked", lambda _, val=t_val: self.dialog_time_entry.set_text(val))
            time_presets.append(b)
        b_clear_t = Gtk.Button(label="Clear")
        b_clear_t.add_css_class('pill-btn')
        b_clear_t.connect("clicked", lambda *_: self.dialog_time_entry.set_text(""))
        time_presets.append(b_clear_t)
        time_box.append(time_presets)

        self.dialog_time_entry = Gtk.Entry()
        self.dialog_time_entry.set_placeholder_text("HH:MM (e.g. 14:30)")
        self.dialog_time_entry.add_css_class('task-entry')
        time_box.append(self.dialog_time_entry)
        form_box.append(time_box)

        # Notes / Description
        notes_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        notes_hdr = Gtk.Label(label="Description / Notes:")
        notes_hdr.set_halign(Gtk.Align.START)
        notes_hdr.add_css_class('dialog-label')
        notes_box.append(notes_hdr)

        notes_scroll = Gtk.ScrolledWindow()
        notes_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        notes_scroll.set_size_request(-1, 70)
        self.dialog_notes_view = Gtk.TextView()
        self.dialog_notes_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.dialog_notes_view.add_css_class('task-notes-view')
        notes_scroll.set_child(self.dialog_notes_view)
        notes_box.append(notes_scroll)
        form_box.append(notes_box)

        # Subtasks container for edit mode
        self.dialog_subtasks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        form_box.append(self.dialog_subtasks_box)

        # Footer Actions
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        footer.set_margin_top(6)

        self.dialog_delete_btn = Gtk.Button(label="🗑 Delete")
        self.dialog_delete_btn.add_css_class('dialog-delete-btn')
        self.dialog_delete_btn.connect("clicked", lambda *_: self._delete_task())
        footer.append(self.dialog_delete_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        footer.append(spacer)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.add_css_class('dialog-cancel-btn')
        cancel_btn.connect("clicked", lambda *_: self.close_task_dialog())
        footer.append(cancel_btn)

        self.dialog_save_btn = Gtk.Button(label="Save")
        self.dialog_save_btn.add_css_class('dialog-save-btn')
        self.dialog_save_btn.connect("clicked", lambda *_: self._save_task())
        footer.append(self.dialog_save_btn)

        self.dialog_card.append(footer)

    def _update_dialog_lists(self, selected_lid=None):
        titles = [tl['title'] for tl in self.task_lists]
        self._dialog_lists = self.task_lists
        model = Gtk.StringList.new(titles if titles else ["Default"])
        self.dialog_list_dropdown.set_model(model)
        selected_idx = 0
        if selected_lid:
            for idx, tl in enumerate(self.task_lists):
                if tl['id'] == selected_lid:
                    selected_idx = idx
                    break
        self.dialog_list_dropdown.set_selected(selected_idx)

    def _update_dialog_parents(self, selected_parent_id=None):
        idx = self.dialog_list_dropdown.get_selected()
        if idx >= len(self._dialog_lists):
            self.dialog_parent_dropdown.set_model(Gtk.StringList.new(["None (Top-level task)"]))
            self._dialog_parent_ids = [None]
            return

        current_tl = self._dialog_lists[idx]
        top_tasks = current_tl.get('tasks', [])
        editing_id = self._dialog_task['id'] if (self._dialog_mode == 'edit' and self._dialog_task) else None

        parent_titles = ["None (Top-level task)"]
        self._dialog_parent_ids = [None]

        for t in top_tasks:
            if editing_id and t['id'] == editing_id:
                continue
            parent_titles.append(f"↳ {t['title']}")
            self._dialog_parent_ids.append(t['id'])

        model = Gtk.StringList.new(parent_titles)
        self.dialog_parent_dropdown.set_model(model)

        selected_pos = 0
        if selected_parent_id:
            for p_idx, pid in enumerate(self._dialog_parent_ids):
                if pid == selected_parent_id:
                    selected_pos = p_idx
                    break
        self.dialog_parent_dropdown.set_selected(selected_pos)

    def _on_dialog_list_changed(self):
        self._update_dialog_parents()

    def _get_selected_list_id(self):
        idx = self.dialog_list_dropdown.get_selected()
        if idx < len(self._dialog_lists):
            return self._dialog_lists[idx]['id']
        return self._dialog_lists[0]['id'] if self._dialog_lists else None

    def _get_selected_parent_id(self):
        idx = self.dialog_parent_dropdown.get_selected()
        if idx < len(self._dialog_parent_ids):
            return self._dialog_parent_ids[idx]
        return None

    def open_task_dialog(self, mode='create', task=None, default_list_id=None, default_parent_id=None, default_date=None):
        self._dialog_mode = mode
        self._dialog_task = task

        while True:
            child = self.dialog_subtasks_box.get_first_child()
            if child is None:
                break
            self.dialog_subtasks_box.remove(child)

        target_lid = default_list_id
        if task:
            target_lid = task.get('lid')
        elif not target_lid and self.task_lists:
            target_lid = self.task_lists[0]['id']

        self._update_dialog_lists(target_lid)
        self._update_dialog_parents(default_parent_id if mode == 'create' else (task.get('parent') if task else None))

        if mode == 'create':
            if default_parent_id:
                p_title = ""
                for tl in self.task_lists:
                    for t in tl.get('tasks', []):
                        if t['id'] == default_parent_id:
                            p_title = t.get('title', '')
                            break
                self.dialog_title_lbl.set_markup(f"<b>New Subtask</b> <span alpha='65%'>under {html.escape(p_title)}</span>")
                self.dialog_save_btn.set_label("Create Subtask")
            else:
                self.dialog_title_lbl.set_markup("<b>New Task</b>")
                self.dialog_save_btn.set_label("Create Task")

            self.dialog_delete_btn.set_visible(False)
            self.dialog_title_entry.set_text("")

            if default_date:
                self.dialog_date_entry.set_text(default_date.isoformat())
            else:
                self.dialog_date_entry.set_text("")

            self.dialog_time_entry.set_text("")
            self.dialog_notes_view.get_buffer().set_text("")

        elif mode == 'edit' and task:
            is_sub = bool(task.get('parent'))
            if is_sub:
                self.dialog_title_lbl.set_markup(f"<b>Edit Subtask</b> <span alpha='65%'>({html.escape(task.get('parent_title', ''))})</span>")
            else:
                self.dialog_title_lbl.set_markup("<b>Edit Task</b>")

            self.dialog_save_btn.set_label("Save Changes")
            self.dialog_delete_btn.set_visible(True)

            self.dialog_title_entry.set_text(task.get('title', ''))
            self.dialog_date_entry.set_text(task.get('due') or '')
            self.dialog_time_entry.set_text(task.get('time') or '')
            self.dialog_notes_view.get_buffer().set_text(task.get('notes') or '')

            subtasks = task.get('subtasks', [])
            if not is_sub:
                subs_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                subs_lbl = Gtk.Label()
                subs_lbl.set_markup(f"<b>Subtasks ({len(subtasks)}):</b>")
                subs_lbl.set_halign(Gtk.Align.START)
                subs_lbl.set_hexpand(True)
                subs_lbl.add_css_class('dialog-label')
                subs_hdr.append(subs_lbl)

                add_sub_inline_btn = Gtk.Button(label="+ Add subtask")
                add_sub_inline_btn.add_css_class('pill-btn')
                add_sub_inline_btn.connect(
                    "clicked",
                    lambda *_: self.open_task_dialog(
                        mode='create',
                        default_list_id=task['lid'],
                        default_parent_id=task['id']
                    )
                )
                subs_hdr.append(add_sub_inline_btn)
                self.dialog_subtasks_box.append(subs_hdr)

                if subtasks:
                    for s in subtasks:
                        s_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                        s_glyph = Gtk.Label(label="↳")
                        s_glyph.add_css_class('subtask-glyph')
                        s_name = Gtk.Label()
                        s_name.set_halign(Gtk.Align.START)
                        s_name.set_hexpand(True)
                        s_name.set_ellipsize(Pango.EllipsizeMode.END)
                        s_name.add_css_class('event-name')
                        if s.get('done'):
                            s_name.set_markup(f"<span alpha='50%'><s>{html.escape(s['title'])}</s></span>")
                        else:
                            s_name.set_text(s['title'])

                        s_edit_btn = Gtk.Button()
                        s_edit_lbl = Gtk.Label(label="\uf044")
                        s_edit_lbl.set_halign(Gtk.Align.CENTER)
                        s_edit_lbl.set_valign(Gtk.Align.CENTER)
                        s_edit_btn.set_child(s_edit_lbl)
                        s_edit_btn.add_css_class('task-row-btn')
                        s_edit_btn.add_css_class('nerd')
                        s_edit_btn.connect("clicked", lambda _, sub_task=s: self.open_task_dialog(mode='edit', task=sub_task))

                        s_toggle = Gtk.Button(label="✓")
                        s_toggle.add_css_class('done-toggle')
                        s_toggle.add_css_class('done-toggle-active' if s.get('done') else 'done-toggle-inactive')
                        s_toggle.connect("clicked", self._on_task_toggle, s)

                        s_row.append(s_glyph)
                        s_row.append(s_name)
                        s_row.append(s_edit_btn)
                        s_row.append(s_toggle)
                        self.dialog_subtasks_box.append(s_row)

        self.dialog_scrim.set_visible(True)
        self.dialog_title_entry.grab_focus()

    def close_task_dialog(self):
        self.dialog_scrim.set_visible(False)
        self._dialog_task = None

    def _save_task(self):
        title = self.dialog_title_entry.get_text().strip()
        if not title:
            self.dialog_title_entry.grab_focus()
            return

        date_str = self.dialog_date_entry.get_text().strip() or None
        time_str = self.dialog_time_entry.get_text().strip() or None
        notes_buf = self.dialog_notes_view.get_buffer()
        notes_text = notes_buf.get_text(notes_buf.get_start_iter(), notes_buf.get_end_iter(), True).strip()

        if time_str:
            if not notes_text.startswith(f"⏰ {time_str}"):
                notes_text = f"⏰ {time_str}\n{notes_text}".strip()

        due_iso = None
        if date_str:
            try:
                datetime.date.fromisoformat(date_str)
                due_iso = f"{date_str}T00:00:00.000Z"
            except ValueError:
                pass

        lid = self._get_selected_list_id()
        parent_id = self._get_selected_parent_id()
        mode = self._dialog_mode
        task = self._dialog_task

        self.dialog_save_btn.set_sensitive(False)
        self.dialog_save_btn.add_css_class('pulsing')

        def do_save():
            try:
                from googleapiclient.discovery import build
                creds = _get_credentials()
                if creds is None:
                    return
                service = build('tasks', 'v1', credentials=creds)

                body = {
                    'title': title,
                    'notes': notes_text if notes_text else '',
                }
                if due_iso:
                    body['due'] = due_iso
                elif mode == 'edit':
                    body['due'] = None

                if mode == 'create':
                    insert_kwargs = {'tasklist': lid, 'body': body}
                    if parent_id:
                        insert_kwargs['parent'] = parent_id
                    service.tasks().insert(**insert_kwargs).execute()
                elif mode == 'edit' and task:
                    service.tasks().patch(tasklist=task['lid'], task=task['id'], body=body).execute()
                    old_parent = task.get('parent')
                    if parent_id != old_parent:
                        move_kwargs = {'tasklist': task['lid'], 'task': task['id']}
                        if parent_id:
                            move_kwargs['parent'] = parent_id
                        service.tasks().move(**move_kwargs).execute()

                _run_sync()

                def after():
                    self.dialog_save_btn.remove_css_class('pulsing')
                    self.dialog_save_btn.set_sensitive(True)
                    self.close_task_dialog()
                    self.app.reload_all_windows()
                    return False
                GLib.idle_add(after)
            except Exception as e:
                print(f'[save task error] {e}', file=sys.stderr)
                def after_err():
                    self.dialog_save_btn.remove_css_class('pulsing')
                    self.dialog_save_btn.set_sensitive(True)
                    return False
                GLib.idle_add(after_err)

        threading.Thread(target=do_save, daemon=True).start()

    def _delete_task(self):
        task = self._dialog_task
        if not task:
            return

        self.dialog_delete_btn.set_sensitive(False)
        self.dialog_delete_btn.add_css_class('pulsing')

        def do_delete():
            try:
                from googleapiclient.discovery import build
                creds = _get_credentials()
                if creds is None:
                    return
                service = build('tasks', 'v1', credentials=creds)
                service.tasks().delete(tasklist=task['lid'], task=task['id']).execute()
                _run_sync()

                def after():
                    self.dialog_delete_btn.remove_css_class('pulsing')
                    self.dialog_delete_btn.set_sensitive(True)
                    self.close_task_dialog()
                    self.app.reload_all_windows()
                    return False
                GLib.idle_add(after)
            except Exception as e:
                print(f'[delete task error] {e}', file=sys.stderr)
                def after_err():
                    self.dialog_delete_btn.remove_css_class('pulsing')
                    self.dialog_delete_btn.set_sensitive(True)
                    return False
                GLib.idle_add(after_err)

        threading.Thread(target=do_delete, daemon=True).start()

    def _draw_refresh_icon(self, da, ctx, width, height):
        r, g, b = self._refresh_fg
        if not hasattr(self, '_refresh_layout'):
            self._refresh_layout = PangoCairo.create_layout(ctx)
            font_name = NERD_FONT.split(',')[0].strip()
            self._refresh_layout.set_font_description(
                Pango.FontDescription.from_string(f"{font_name} 12"))
            self._refresh_layout.set_text("\uf021")
            ink, _ = self._refresh_layout.get_pixel_extents()
            self._refresh_ink = ink
        else:
            PangoCairo.update_layout(ctx, self._refresh_layout)

        ink = self._refresh_ink
        x = (width - ink.width) / 2 - ink.x
        y = (height - ink.height) / 2 - ink.y

        if self._refresh_angle != 0.0:
            ctx.translate(width / 2, height / 2)
            ctx.rotate(self._refresh_angle)
            ctx.translate(-width / 2, -height / 2)

        ctx.set_source_rgba(r, g, b, 1.0)
        ctx.move_to(x, y)
        PangoCairo.show_layout(ctx, self._refresh_layout)

    def _on_refresh_clicked(self, _):
        self.refresh_btn.set_sensitive(False)

        def tick():
            self._refresh_angle += 0.15
            self._refresh_da.queue_draw()
            return not self.refresh_btn.get_sensitive()
        self._refresh_spin_timer = GLib.timeout_add(16, tick)

        def do_sync():
            _run_sync()
            def after():
                if self._refresh_spin_timer:
                    GLib.source_remove(self._refresh_spin_timer)
                    self._refresh_spin_timer = None
                self._refresh_angle = 0.0
                self._refresh_da.queue_draw()
                self.app.reload_all_windows()
                self.refresh_btn.set_sensitive(True)
                return False
            GLib.idle_add(after)
        threading.Thread(target=do_sync, daemon=True).start()

    def _navigate(self, delta):
        self.month += delta
        if self.month < 1:
            self.month = 12
            self.year -= 1
        elif self.month > 12:
            self.month = 1
            self.year += 1
        self.month_label.set_markup(
            f"<b>{datetime.date(self.year, self.month, 1).strftime('%B %Y').upper()}</b>"
        )
        self._build_grid()

    def reload_data(self):
        """Reload events and task lists from disk cache and re-render."""
        self.events, self.task_lists = load_data()
        self.current_theme = load_theme()
        self._update_clock()
        self._update_stats_pills()
        self.month_label.set_markup(
            f"<b>{datetime.date(self.year, self.month, 1).strftime('%B %Y').upper()}</b>"
        )
        self._build_grid()
        self._update_agenda_card(self.selected_date)
        self._populate_task_boards()

    def reload_theme(self):
        """Reload theme settings and re-apply styling."""
        self.current_theme = load_theme()
        self._apply_css()
        self.reload_data()

    def reload_config(self):
        """Live update layout when config.json changes."""
        self.config = load_config()
        self.cal_width = self._calc_calendar_width()

        self.left_col.set_size_request(self.cal_width, -1)
        self.left_col.set_hexpand(False)
        self.left_col.set_homogeneous(True)

        if hasattr(self, 'calendar_card'):
            self.calendar_card.set_vexpand(True)
        if hasattr(self, 'agenda_card'):
            self.agenda_card.set_vexpand(True)

        fill_rest = self.config.get('task_panels_fill_rest', True)
        if hasattr(self, 'boards_box'):
            self.boards_box.set_homogeneous(fill_rest)

        self._apply_css()
        self.reload_data()

    def _apply_css(self):
        th = getattr(self, 'current_theme', None) or load_theme()
        fg = th.get('text_fg', '#d8deda')
        accent = th.get('accent', '#94baa6')
        red = '#c97f88'
        self._refresh_fg = hex_to_rgb_float(fg)

        col_css_lines = []
        for cth in th.get('column_themes', []):
            col_css_lines.append(f"""
      /* Theme: {cth['name']} */
      .kanban-theme-{cth['name']} {{
          background: {cth['bg_card']};
          border: 1px solid {cth['border']};
      }}
      .accent-bg-{cth['name']} {{ background: {cth['grad']}; }}
      .badge-{cth['name']} {{ background: {cth['badge_bg']}; color: {cth['color']}; border: 1px solid {cth['border']}; }}
      .btn-{cth['name']} {{ background: {cth['badge_bg']}; color: {cth['color']}; }}
      .footer-btn-{cth['name']} {{ background: {cth['badge_bg']}; color: {cth['color']}; border-color: {cth['border']}; }}
""")
        column_styles = "\n".join(col_css_lines)

        css = f"""
      window {{
          background: transparent;
      }}
      /* Desktop background canvas */
      .desktop-bg {{
          background: {th.get('desktop_bg', 'linear-gradient(135deg, rgba(22, 27, 25, 0.94), rgba(18, 22, 20, 0.94))')};
          border-radius: 16px;
          border: 1px solid {th.get('desktop_border', 'rgba(255, 255, 255, 0.08)')};
          padding: 8px 12px;
      }}
      .desktop-card {{
          border-radius: 12px;
          padding: 10px;
      }}
      .desktop-header-card {{
          background: {th.get('card_bg', 'rgba(33, 40, 37, 0.90)')};
          border: 1px solid {th.get('card_border', 'rgba(255, 255, 255, 0.06)')};
          border-radius: 12px;
          padding: 6px 14px;
      }}
      .calendar-card {{
          background: {th.get('card_bg', 'rgba(33, 40, 37, 0.90)')};
          border: 1px solid {th.get('card_border', 'rgba(255, 255, 255, 0.06)')};
      }}
      .agenda-card {{
          background: {th.get('card_bg', 'rgba(33, 40, 37, 0.90)')};
          border: 1px solid {th.get('card_border', 'rgba(255, 255, 255, 0.06)')};
      }}
      .header-date {{
          font-size: 13px;
          font-weight: bold;
          color: {th.get('text_fg', '#d8deda')};
      }}
      .header-clock {{
          font-size: 13px;
          font-family: monospace;
          color: {th.get('accent', '#94baa6')};
          font-weight: bold;
      }}
      .status-pill {{
          border-radius: 8px;
          padding: 3px 9px;
          font-size: 10.5px;
          font-weight: 500;
      }}
      .pill-due {{
          border: 1px solid rgba(202, 160, 140, 0.35);
          background: rgba(202, 160, 140, 0.16);
          color: #caa08c;
      }}
      .pill-pending {{
          border: 1px solid rgba(255, 255, 255, 0.12);
          background: rgba(255, 255, 255, 0.07);
          color: {th.get('text_fg', '#d8deda')};
      }}
      .pill-lists {{
          border: 1px solid rgba(130, 164, 184, 0.35);
          background: rgba(130, 164, 184, 0.16);
          color: #82a4b8;
      }}
      button {{
          background: transparent;
          border: 1px solid transparent;
          border-radius: 8px;
          color: {fg};
          font-size: 11px;
          font-weight: 500;
      }}
      button:hover {{
          background: rgba(255, 255, 255, 0.08);
      }}
      button:active {{
          background: rgba(255, 255, 255, 0.18);
      }}
      button:focus,
      button:focus-visible {{
          outline: none;
          box-shadow: none;
      }}
      label {{
          color: {fg};
      }}
      .action-btn {{
          background: rgba(255, 255, 255, 0.06);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 8px;
          color: {fg};
          font-size: 11px;
          padding: 4px 10px;
      }}
      .action-btn:hover {{
          background: rgba(255, 255, 255, 0.12);
          border-color: rgba(255, 255, 255, 0.22);
      }}
      .action-btn-primary {{
          background: {th.get('save_btn_bg', '#44544d')};
          border: 1px solid {th.get('today_border', 'rgba(148, 186, 166, 0.35)')};
          border-radius: 8px;
          color: {th.get('today_fg', '#e8efe9')};
          font-weight: bold;
          font-size: 11px;
          padding: 4px 12px;
          box-shadow: none;
      }}
      .action-btn-primary:hover {{
          background: {th.get('save_btn_hover', '#50635b')};
      }}
      .calendar-title {{
          font-size: 11px;
          font-weight: bold;
          color: {fg};
      }}
      .nav-btn {{
          padding: 1px 6px;
          font-size: 13px;
          color: rgba(216, 222, 218, 0.7);
      }}
      .nav-btn:hover {{
          color: #ffffff;
      }}
      .weekday {{
          color: rgba(216, 222, 218, 0.45);
          font-size: 10px;
          font-weight: 600;
      }}
      .other-month {{
          opacity: 0.2;
      }}
      .weekend {{
          background: rgba(255, 255, 255, 0.03);
          border-radius: 6px;
      }}
      .weekend-label {{
          color: #9aa6a0;
      }}
      .today {{
          background: {th.get('today_bg', '#44544d')};
          border: 1px solid {th.get('today_border', 'rgba(148, 186, 166, 0.35)')};
          border-radius: 6px;
          font-weight: bold;
          color: {th.get('today_fg', '#e8efe9')};
          box-shadow: none;
      }}
      .today:hover {{
          background: {th.get('save_btn_hover', '#50635b')};
      }}
      .selected {{
          border: 2px solid {accent};
          border-radius: 6px;
      }}
      .today.selected {{
          border: 2px solid #ffffff;
      }}
      .event-bar {{
          background: {accent};
          border-radius: 2px;
          min-height: 2px;
      }}
      .task-bar {{
          background: #caa08c;
          border-radius: 2px;
          min-height: 2px;
      }}
      .agenda-heading {{
          font-size: 11.5px;
          margin-bottom: 2px;
          color: {fg};
      }}
      .agenda-row {{
          background: rgba(255, 255, 255, 0.035);
          border: 1px solid rgba(255, 255, 255, 0.06);
          border-radius: 6px;
          padding: 3px 6px;
      }}
      .event-dot {{
          color: {accent};
          font-size: 10px;
      }}
      .event-name {{
          font-size: 11px;
          color: {fg};
      }}
      .task-dot {{
          color: #caa08c;
          font-size: 10px;
      }}
      .done-dot {{
          color: #94baa6;
          font-size: 10px;
      }}
      .done-toggle {{
          font-size: 10px;
          min-width: 17px;
          min-height: 17px;
          padding: 0;
          border-radius: 4px;
      }}
      .done-toggle-inactive {{
          border: 1px solid rgba(255, 255, 255, 0.2);
          color: transparent;
      }}
      .done-toggle-inactive:hover {{
          border-color: #94baa6;
          color: #94baa6;
      }}
      .done-toggle-active {{
          border: 1px solid #94baa6;
          color: #94baa6;
          background: rgba(148, 186, 166, 0.2);
      }}
      .no-events {{
          font-size: 11px;
          color: rgba(216, 222, 218, 0.4);
          font-style: italic;
      }}
      .add-btn {{
          background: rgba(255, 255, 255, 0.06);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 6px;
          color: {fg};
          font-size: 10.5px;
          padding: 3px 0;
      }}
      .add-btn:hover {{
          background: rgba(255, 255, 255, 0.12);
      }}

      /* ── Kanban Column Themes ──────────────────────────────── */
      .kanban-column {{
          padding: 8px 10px 10px 10px;
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
      }}
      .kanban-top-bar {{
          border-radius: 3px;
          margin-bottom: 4px;
      }}
      .kanban-title {{
          font-size: 11px;
          font-weight: bold;
      }}
      .kanban-count-badge {{
          font-size: 9px;
          font-weight: 600;
          border-radius: 5px;
          padding: 1px 5px;
      }}
      .theme-add-btn {{
          font-size: 11px;
          min-width: 18px;
          min-height: 18px;
          border-radius: 4px;
          padding: 0;
          font-weight: bold;
      }}
      .task-item-card {{
          background: rgba(255, 255, 255, 0.035);
          border: 1px solid rgba(255, 255, 255, 0.06);
          border-radius: 7px;
          padding: 3px 6px;
      }}
      .task-item-card:hover {{
          background: rgba(255, 255, 255, 0.07);
          border-color: rgba(255, 255, 255, 0.12);
      }}

{column_styles}

      /* ── Due Badges ────────────────────────────────────────── */
      .due-today {{
          background: rgba(202, 160, 140, 0.22);
          color: #caa08c;
          border: 1px solid rgba(202, 160, 140, 0.45);
          border-radius: 4px;
          padding: 1px 4px;
          font-size: 8.5pt;
          font-weight: bold;
      }}
      .due-overdue {{
          background: rgba(201, 127, 136, 0.22);
          color: #c97f88;
          border: 1px solid rgba(201, 127, 136, 0.45);
          border-radius: 4px;
          padding: 1px 4px;
          font-size: 8.5pt;
          font-weight: bold;
      }}
      .due-future {{
          background: rgba(148, 186, 166, 0.18);
          color: #94baa6;
          border: 1px solid rgba(148, 186, 166, 0.35);
          border-radius: 4px;
          padding: 1px 4px;
          font-size: 8.5pt;
      }}

      /* ── Footer & Subtasks ─────────────────────────────────── */
      .kanban-footer-btn {{
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 6px;
          color: {fg};
          font-size: 10.5px;
          padding: 3px 0;
      }}
      .kanban-footer-btn:hover {{
          background: rgba(255, 255, 255, 0.12);
      }}
      .task-entry {{
          background: rgba(255, 255, 255, 0.08);
          border: 1px solid rgba(255, 255, 255, 0.15);
          border-radius: 6px;
          color: {fg};
          font-size: 11px;
          padding: 3px 8px;
      }}
      .task-entry:focus {{
          border-color: {accent};
          background: rgba(255, 255, 255, 0.12);
      }}
      .task-title-btn {{
          background: transparent;
          border: none;
          padding: 1px 2px;
          margin: 0;
          border-radius: 4px;
      }}
      .task-title-btn:hover {{
          background: rgba(255, 255, 255, 0.06);
      }}
      .subtask-glyph {{
          font-size: 10px;
          margin-right: 2px;
      }}
      .subtask-badge {{
          font-size: 8.5pt;
          border-radius: 4px;
          padding: 1px 4px;
          font-weight: 600;
      }}
      .subtasks-toggle-btn {{
          padding: 0 3px;
          min-width: 15px;
          min-height: 15px;
          border-radius: 4px;
      }}
      .subtasks-toggle-btn:hover {{
          background: rgba(255, 255, 255, 0.1);
      }}
      .task-row-btn {{
          font-size: 10px;
          min-width: 17px;
          min-height: 17px;
          padding: 0;
          border-radius: 4px;
          color: rgba(216, 222, 218, 0.6);
      }}
      .task-row-btn:hover {{
          color: #ffffff;
          background: rgba(255, 255, 255, 0.14);
      }}
      .task-row-btn.nerd label {{
          all: unset;
          font-family: "{NERD_FONT}";
          font-size: 10px;
          color: rgba(216, 222, 218, 0.6);
      }}
      .task-row-btn.nerd:hover label {{
          color: #ffffff;
      }}
      .dialog-scrim {{
          background: rgba(0, 0, 0, 0.65);
      }}
      .dialog-card {{
          background: {th.get('dialog_bg', 'rgba(28, 34, 31, 0.98)')};
          border: 1px solid {th.get('card_border', 'rgba(255, 255, 255, 0.12)')};
          border-radius: 14px;
          padding: 16px;
          box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
      }}
      .dialog-title {{
          font-size: 13px;
          font-weight: bold;
          color: {th.get('text_fg', '#d8deda')};
      }}
      .dialog-close-btn {{
          color: rgba(216, 222, 218, 0.6);
          font-size: 12px;
          padding: 2px 6px;
          border-radius: 6px;
      }}
      .dialog-close-btn:hover {{
          color: #ffffff;
          background: rgba(255, 255, 255, 0.1);
      }}
      .dialog-label {{
          font-size: 11px;
          font-weight: 500;
          color: rgba(216, 222, 218, 0.75);
      }}
      .pill-btn {{
          background: rgba(255, 255, 255, 0.08);
          border: 1px solid rgba(255, 255, 255, 0.16);
          border-radius: 6px;
          color: {fg};
          font-size: 10px;
          padding: 2px 6px;
      }}
      .pill-btn:hover {{
          background: rgba(255, 255, 255, 0.16);
          border-color: rgba(255, 255, 255, 0.3);
      }}
      .task-notes-view {{
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.15);
          border-radius: 8px;
          color: {th.get('text_fg', '#d8deda')};
          font-size: 11px;
          padding: 6px;
      }}
      .task-notes-view:focus {{
          border-color: {accent};
          background: rgba(255, 255, 255, 0.08);
      }}
      .dialog-save-btn {{
          background: {th.get('save_btn_bg', '#44544d')};
          border: 1px solid {th.get('today_border', 'rgba(148, 186, 166, 0.35)')};
          border-radius: 8px;
          color: {th.get('today_fg', '#e8efe9')};
          font-weight: 600;
          font-size: 11px;
          padding: 5px 14px;
          box-shadow: none;
      }}
      .dialog-save-btn:hover {{
          background: {th.get('save_btn_hover', '#50635b')};
      }}
      .dialog-delete-btn {{
          background: rgba(201, 127, 136, 0.18);
          border: 1px solid rgba(201, 127, 136, 0.45);
          border-radius: 8px;
          color: #c97f88;
          font-size: 11px;
          padding: 5px 10px;
      }}
      .dialog-delete-btn:hover {{
          background: rgba(201, 127, 136, 0.32);
      }}
      .dialog-cancel-btn {{
          background: rgba(255, 255, 255, 0.08);
          border: 1px solid rgba(255, 255, 255, 0.15);
          border-radius: 8px;
          color: {fg};
          font-size: 11px;
          padding: 5px 10px;
      }}
      .dialog-cancel-btn:hover {{
          background: rgba(255, 255, 255, 0.15);
      }}
      dropdown {{
          background: rgba(255, 255, 255, 0.07);
          border: 1px solid rgba(255, 255, 255, 0.15);
          border-radius: 8px;
          color: {th.get('text_fg', '#d8deda')};
          font-size: 11px;
          padding: 2px 6px;
      }}
      dropdown:focus {{
          border-color: {accent};
      }}
      @keyframes pulse {{
          0%, 100% {{ opacity: 1; }}
          50%       {{ opacity: 0.25; }}
      }}
      .pulsing {{
          animation: pulse 0.6s ease-in-out infinite;
      }}
      .day-number {{
          font-size: 13px;
          font-weight: 500;
      }}
      """.encode()

        if not hasattr(self, '_css_provider'):
            self._css_provider = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(), self._css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        self._css_provider.load_from_data(css)


class DesktopBackgroundApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.waybar.ycal.background")
        self.windows = []
        self._file_monitor = None
        self._config_monitor = None
        self._theme_monitor = None

    def do_activate(self):
        display = Gdk.Display.get_default()
        monitors = display.get_monitors()

        def create_windows():
            for w in self.windows:
                w.destroy()
            self.windows = []

            n = monitors.get_n_items()
            if n == 0:
                w = DesktopBackgroundWindow(self, None)
                w.present()
                self.windows.append(w)
            else:
                for i in range(n):
                    m = monitors.get_item(i)
                    w = DesktopBackgroundWindow(self, m)
                    w.present()
                    self.windows.append(w)

        create_windows()
        monitors.connect("items-changed", lambda *_: create_windows())

        # Live clock update every 1 second
        GLib.timeout_add_seconds(1, self._tick_clock)

        # File monitor on CACHE_FILE for instant live sync with Waybar popup
        self._setup_file_monitor()
        # Theme monitor for instant theme switching without restart
        self._setup_theme_monitor()
        # Config monitor for instant layout adjustments
        self._setup_config_monitor()

        # Write PID file
        os.makedirs(os.path.dirname(BG_PID_FILE), exist_ok=True)
        with open(BG_PID_FILE, 'w') as f:
            f.write(str(os.getpid()))

        # Periodic background sync every 15 minutes
        GLib.timeout_add_seconds(SYNC_INTERVAL_SEC, lambda: threading.Thread(target=_run_sync, daemon=True).start() or True)

    def _tick_clock(self):
        for w in self.windows:
            w._update_clock()
        return True

    def _setup_file_monitor(self):
        try:
            gfile = Gio.File.new_for_path(CACHE_FILE)
            self._file_monitor = gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
            self._file_monitor.connect("changed", self._on_file_changed)
        except Exception as e:
            print(f'[bg file monitor error] {e}', file=sys.stderr)

    def _on_file_changed(self, monitor, file, other_file, event_type):
        if event_type in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED):
            GLib.idle_add(self.reload_all_windows)

    def reload_all_windows(self):
        for w in self.windows:
            w.reload_data()
        return False

    def _setup_theme_monitor(self):
        try:
            os.makedirs(os.path.dirname(CURRENT_THEME_FILE), exist_ok=True)
            if not os.path.exists(CURRENT_THEME_FILE):
                with open(CURRENT_THEME_FILE, 'w') as f:
                    json.dump(DEFAULT_THEME, f, indent=2)
            gfile = Gio.File.new_for_path(CURRENT_THEME_FILE)
            self._theme_monitor = gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
            self._theme_monitor.connect("changed", self._on_theme_changed)
        except Exception as e:
            print(f'[bg theme monitor error] {e}', file=sys.stderr)

    def _on_theme_changed(self, monitor, file, other_file, event_type):
        if event_type in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED):
            GLib.idle_add(self.retheme_all_windows)

    def retheme_all_windows(self):
        for w in self.windows:
            w.reload_theme()
        return False

    def _setup_config_monitor(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            if not os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(DEFAULT_CONFIG, f, indent=2)
            gfile = Gio.File.new_for_path(CONFIG_FILE)
            self._config_monitor = gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
            self._config_monitor.connect("changed", self._on_config_changed)
        except Exception as e:
            print(f'[bg config monitor error] {e}', file=sys.stderr)

    def _on_config_changed(self, monitor, file, other_file, event_type):
        if event_type in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED):
            GLib.idle_add(self.reconfig_all_windows)

    def reconfig_all_windows(self):
        for w in self.windows:
            w.reload_config()
        return False


def main():
    app = DesktopBackgroundApp()
    try:
        app.run(None)
    finally:
        if os.path.exists(BG_PID_FILE):
            os.remove(BG_PID_FILE)


if __name__ == '__main__':
    main()

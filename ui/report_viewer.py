import threading
from datetime import datetime, timedelta

import customtkinter as ctk

from config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_BORDER, score_color,
)
from ui.widgets.activity_chart import ActivityChart
from ui.widgets.screenshot_gallery import ScreenshotGallery


def _fmt_seconds(s: int) -> str:
    h = s // 3600
    m = (s % 3600) // 60
    return f"{h}h {m:02d}m"


class ReportViewer(ctk.CTkFrame):
    def __init__(self, master, session, storage, employee=None, **kwargs):
        super().__init__(master, fg_color=COLOR_BG, corner_radius=0, **kwargs)
        self._session = session
        self._storage = storage
        self._target_employee = employee
        self._selected_employee_id = None
        self._current_date = datetime.now().date()
        self._load_token = 0  # incremented each load; stale threads check this
        self._build()

    def _build(self):
        # Header
        ctk.CTkLabel(
            self,
            text="Activity Reports",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        ).pack(fill="x", padx=24, pady=(20, 8))

        # Control bar
        ctrl = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12)
        ctrl.pack(fill="x", padx=24, pady=(0, 12))
        ctrl_inner = ctk.CTkFrame(ctrl, fg_color="transparent")
        ctrl_inner.pack(padx=16, pady=12, fill="x")

        # Employee selector (admin only)
        if self._session.is_admin():
            ctk.CTkLabel(
                ctrl_inner, text="Employee:",
                font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED,
            ).pack(side="left", padx=(0, 8))

            accounts = self._storage.get_all_accounts()
            self._employees = [a for a in accounts if not a.is_admin()]
            names = [f"{e.display_name} ({e.username})" for e in self._employees]

            if not names:
                names = ["No employees"]

            self._emp_var = ctk.StringVar(value=names[0] if names else "")
            if self._target_employee:
                for i, e in enumerate(self._employees):
                    if e.id == self._target_employee.id:
                        self._emp_var.set(names[i])
                        break

            self._emp_dropdown = ctk.CTkOptionMenu(
                ctrl_inner,
                values=names,
                variable=self._emp_var,
                command=self._on_employee_change,
                width=200,
            )
            self._emp_dropdown.pack(side="left", padx=(0, 16))

        # Date navigation
        ctk.CTkButton(
            ctrl_inner, text="◀", width=36, height=32,
            fg_color="#333", hover_color="#555",
            command=self._prev_day,
        ).pack(side="left")

        self._date_label = ctk.CTkLabel(
            ctrl_inner,
            text=self._current_date.strftime("%A, %B %d, %Y"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXT,
            width=220, anchor="center",
        )
        self._date_label.pack(side="left", padx=4)

        ctk.CTkButton(
            ctrl_inner, text="▶", width=36, height=32,
            fg_color="#333", hover_color="#555",
            command=self._next_day,
        ).pack(side="left")

        ctk.CTkButton(
            ctrl_inner, text="Today", width=70, height=32,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            font=ctk.CTkFont(size=11),
            command=self._go_today,
        ).pack(side="left", padx=(8, 0))

        # Tabs
        self._tabview = ctk.CTkTabview(self, fg_color=COLOR_CARD, corner_radius=12)
        self._tabview.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self._tab_activity = self._tabview.add("Activity Log")
        self._tab_chart = self._tabview.add("Hourly Chart")
        self._tab_screenshots = self._tabview.add("Screenshots")

        self.after(50, self._load_data)

    def _resolve_employee_id(self) -> str:
        if not self._session.is_admin():
            return self._session.current_user.id
        if not hasattr(self, "_employees") or not self._employees:
            return ""
        selected = self._emp_var.get()
        for i, e in enumerate(self._employees):
            if f"{e.display_name} ({e.username})" == selected:
                return e.id
        return self._employees[0].id if self._employees else ""

    # ------------------------------------------------------------------ #
    # Load data — shows "Loading…" immediately, fetches DB in background
    # ------------------------------------------------------------------ #

    def _load_data(self):
        if not self.winfo_exists():
            return
        self._date_label.configure(text=self._current_date.strftime("%A, %B %d, %Y"))
        emp_id = self._resolve_employee_id()
        if not emp_id:
            return

        self._show_loading()

        # Bump token — background threads with an old token are discarded
        self._load_token += 1
        token = self._load_token
        date_str = self._current_date.strftime("%Y-%m-%d")

        threading.Thread(
            target=self._fetch_data_bg,
            args=(emp_id, date_str, token),
            daemon=True,
        ).start()

        # Safety net: if loading hasn't resolved in 10 s, show an error
        self.after(10000, lambda t=token: self._loading_timeout(t))

    def _loading_timeout(self, token: int):
        if not self.winfo_exists():
            return
        if self._load_token != token:
            return  # already resolved by a newer load
        # Still showing "Loading…" — replace with error in any tab that has it
        for tab in (self._tab_activity, self._tab_chart, self._tab_screenshots):
            children = tab.winfo_children()
            if len(children) == 1:
                txt = getattr(children[0], "_text", None) or ""
                if "Loading" in str(txt):
                    children[0].configure(
                        text="Could not load data.\nCheck DB connection.",
                        text_color=COLOR_TEXT_MUTED,
                    )

    def _show_loading(self):
        for tab in (self._tab_activity, self._tab_chart, self._tab_screenshots):
            for w in tab.winfo_children():
                w.destroy()
            ctk.CTkLabel(
                tab, text="Loading…",
                font=ctk.CTkFont(size=13),
                text_color=COLOR_TEXT_MUTED,
            ).pack(expand=True, pady=40)

    def _fetch_data_bg(self, emp_id: str, date_str: str, token: int):
        try:
            activity = self._storage.load_activity(emp_id, date_str)
            hourly = self._storage.get_hourly_scores(emp_id, date_str)
            paths = self._storage.get_all_screenshots_for_date(emp_id, date_str)
        except Exception as exc:
            if self.winfo_exists() and self._load_token == token:
                msg = str(exc)
                self.after(0, lambda m=msg: self._show_error(m))
            return

        if self.winfo_exists() and self._load_token == token:
            self.after(
                0,
                lambda a=activity, h=hourly, p=paths, ds=date_str:
                    self._apply_all(a, h, p, ds),
            )

    def _show_error(self, msg: str = ""):
        for tab in (self._tab_activity, self._tab_chart, self._tab_screenshots):
            for w in tab.winfo_children():
                w.destroy()
            ctk.CTkLabel(
                tab,
                text=f"Could not load data.\n{msg}",
                font=ctk.CTkFont(size=12),
                text_color=COLOR_TEXT_MUTED,
            ).pack(expand=True, pady=40)

    def _apply_all(self, activity, hourly, paths, date_str):
        """Build all three tabs independently — one tab's failure won't block the others."""
        if not self.winfo_exists():
            return
        for builder, tab, args in [
            (self._build_activity_tab,    self._tab_activity,    (activity,)),
            (self._build_chart_tab,       self._tab_chart,       (hourly, date_str)),
            (self._build_screenshots_tab, self._tab_screenshots, (paths,)),
        ]:
            try:
                builder(*args)
            except Exception as exc:
                # Clear the tab and show the specific error so it's visible
                for w in tab.winfo_children():
                    try:
                        w.destroy()
                    except Exception:
                        pass
                ctk.CTkLabel(
                    tab,
                    text=f"Error building tab:\n{exc}",
                    font=ctk.CTkFont(size=11),
                    text_color=COLOR_TEXT_MUTED,
                ).pack(expand=True, pady=40)

    # ------------------------------------------------------------------ #
    # Tab builders — called on main thread with pre-fetched data
    # ------------------------------------------------------------------ #

    def _build_activity_tab(self, activity: dict):
        for w in self._tab_activity.winfo_children():
            w.destroy()

        sessions = activity.get("sessions", [])
        if not sessions:
            ctk.CTkLabel(
                self._tab_activity,
                text="No activity recorded for this date.",
                text_color=COLOR_TEXT_MUTED,
                font=ctk.CTkFont(size=13),
            ).pack(pady=40)
            return

        table = ctk.CTkScrollableFrame(self._tab_activity, fg_color="transparent")
        table.pack(fill="both", expand=True, padx=4, pady=4)

        # ── Day Summary ────────────────────────────────────────────── #
        day_total_s  = sum(s.get("summary", {}).get("total_active_seconds", 0)
                           + s.get("summary", {}).get("total_idle_seconds", 0)
                           for s in sessions)
        day_active_s = sum(s.get("summary", {}).get("total_active_seconds", 0) for s in sessions)
        day_idle_s   = sum(s.get("summary", {}).get("total_idle_seconds",  0) for s in sessions)

        day_card = ctk.CTkFrame(table, fg_color="#0f3460", corner_radius=10)
        day_card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            day_card, text="Day Total",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT, anchor="w",
        ).pack(anchor="w", padx=14, pady=(8, 4))

        day_stats_row = ctk.CTkFrame(day_card, fg_color="transparent")
        day_stats_row.pack(fill="x", padx=12, pady=(0, 10))
        for label, val in [
            ("Total Time",  _fmt_seconds(day_total_s)),
            ("Active Time", _fmt_seconds(day_active_s)),
            ("Idle Time",   _fmt_seconds(day_idle_s)),
            ("Sessions",    str(len(sessions))),
        ]:
            f = ctk.CTkFrame(day_stats_row, fg_color="#1a4a7a", corner_radius=6)
            f.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(f, text=val, font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=COLOR_TEXT).pack(padx=12, pady=(4, 0))
            ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=10),
                         text_color=COLOR_TEXT_MUTED).pack(padx=12, pady=(0, 4))

        # ── Per-Session Cards ──────────────────────────────────────── #
        for session in sessions:
            login = (session.get("login_time") or "")[:19]
            logout_raw = session.get("logout_time")
            logout = logout_raw[:19] if logout_raw else "Active"

            s = session.get("summary", {})
            active_s = s.get("total_active_seconds", 0)
            idle_s   = s.get("total_idle_seconds", 0)
            total_s  = active_s + idle_s

            sess_card = ctk.CTkFrame(table, fg_color=COLOR_CARD, corner_radius=8)
            sess_card.pack(fill="x", pady=4)

            header_row = ctk.CTkFrame(sess_card, fg_color="transparent")
            header_row.pack(fill="x", padx=12, pady=(8, 4))
            ctk.CTkLabel(
                header_row,
                text=f"Session  {login}  →  {logout}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXT,
            ).pack(side="left")

            score = s.get("average_productivity_score", 0.0)
            ctk.CTkLabel(
                header_row,
                text=f"Avg Score: {score}%",
                font=ctk.CTkFont(size=12),
                text_color=score_color(score),
            ).pack(side="right")

            stats_row = ctk.CTkFrame(sess_card, fg_color="transparent")
            stats_row.pack(fill="x", padx=12, pady=(0, 8))
            stats = [
                ("Total Time",   _fmt_seconds(total_s)),
                ("Active Time",  _fmt_seconds(active_s)),
                ("Idle Time",    _fmt_seconds(idle_s)),
                ("Keystrokes",   f"{s.get('total_keystrokes', 0):,}"),
                ("Clicks",       f"{s.get('total_clicks', 0):,}"),
                ("Screenshots",  str(s.get("screenshots_count", 0))),
            ]
            for label, val in stats:
                f = ctk.CTkFrame(stats_row, fg_color="#1e2d4a", corner_radius=6)
                f.pack(side="left", padx=(0, 6))
                ctk.CTkLabel(f, text=val, font=ctk.CTkFont(size=13, weight="bold"),
                             text_color=COLOR_TEXT).pack(padx=10, pady=(4, 0))
                ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=10),
                             text_color=COLOR_TEXT_MUTED).pack(padx=10, pady=(0, 4))

            buckets = session.get("buckets", [])
            if buckets:
                bucket_frame = ctk.CTkScrollableFrame(sess_card, fg_color="transparent", height=150)
                bucket_frame.pack(fill="x", padx=8, pady=(0, 8))

                hdr = ctk.CTkFrame(bucket_frame, fg_color="transparent")
                hdr.pack(fill="x")
                for col in ["Time", "Keystrokes", "Clicks", "Scroll", "Idle(s)", "Score"]:
                    ctk.CTkLabel(hdr, text=col, font=ctk.CTkFont(size=10, weight="bold"),
                                 text_color=COLOR_TEXT_MUTED, anchor="w",
                                 ).pack(side="left", expand=True, fill="x", padx=4)

                for b in buckets:
                    time_str = b.get("minute_bucket", "")[-8:-3]
                    score_val = b.get("productivity_score", 0)
                    brow = ctk.CTkFrame(bucket_frame, fg_color="transparent")
                    brow.pack(fill="x")
                    for val, color in [
                        (time_str, COLOR_TEXT_MUTED),
                        (str(b.get("keystrokes", 0)), COLOR_TEXT),
                        (str(b.get("mouse_clicks", 0)), COLOR_TEXT),
                        (str(b.get("mouse_scroll_ticks", 0)), COLOR_TEXT),
                        (str(b.get("idle_seconds", 0)), COLOR_TEXT),
                        (f"{score_val}%", score_color(score_val)),
                    ]:
                        ctk.CTkLabel(brow, text=val, font=ctk.CTkFont(size=11),
                                     text_color=color, anchor="w",
                                     ).pack(side="left", expand=True, fill="x", padx=4)

    def _build_chart_tab(self, hourly: list, date_str: str):
        for w in self._tab_chart.winfo_children():
            w.destroy()
        chart = ActivityChart(self._tab_chart, title=f"Hourly Productivity — {date_str}")
        chart.pack(fill="both", expand=True, padx=8, pady=8)
        chart.set_data(hourly)

    def _build_screenshots_tab(self, paths: list):
        for w in self._tab_screenshots.winfo_children():
            w.destroy()
        gallery = ScreenshotGallery(self._tab_screenshots)
        gallery.pack(fill="both", expand=True)
        gallery.load_screenshots(paths)

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #

    def _prev_day(self):
        self._current_date -= timedelta(days=1)
        self.after(0, self._load_data)

    def _next_day(self):
        if self._current_date < datetime.now().date():
            self._current_date += timedelta(days=1)
            self.after(0, self._load_data)

    def _go_today(self):
        self._current_date = datetime.now().date()
        self._load_data()

    def _on_employee_change(self, _):
        self._load_data()

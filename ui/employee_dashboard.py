import threading
from datetime import datetime

import customtkinter as ctk

from config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER,
)
from ui.widgets.stat_card import StatCard
from ui.widgets.activity_chart import ActivityChart

# How many 5-second ticks before a full DB refresh
_DB_REFRESH_EVERY_N_TICKS = 12   # = 60 seconds


def _fmt_seconds(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m:02d}m"



class EmployeeDashboard(ctk.CTkFrame):
    def __init__(self, master, session, storage, tracker=None, **kwargs):
        super().__init__(master, fg_color=COLOR_BG, corner_radius=0, **kwargs)
        self._session = session
        self._storage = storage
        self._tracker = tracker
        self._refreshing = False          # guard: only one DB fetch at a time
        # Start counter at threshold so the very first _refresh() triggers a DB fetch
        self._tick_counter = _DB_REFRESH_EVERY_N_TICKS
        self._last_hourly: list = []      # avoid redrawing chart when data unchanged

        self._build()
        self._refresh()        # fires DB fetch immediately (counter already at threshold)
        self._schedule_refresh()

    # ------------------------------------------------------------------ #
    # Build
    # ------------------------------------------------------------------ #

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        self._scroll = scroll

        # ── Header ─────────────────────────────────────────────────── #
        header = ctk.CTkFrame(scroll, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 0))

        emp = self._session.current_user
        ctk.CTkLabel(
            header,
            text=f"Welcome, {emp.display_name}",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        ).pack(side="left")

        self._time_label = ctk.CTkLabel(
            header, text="",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
        )
        self._time_label.pack(side="right")

        # ── Shift Control Card ─────────────────────────────────────── #
        shift_card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=16)
        shift_card.pack(fill="x", padx=24, pady=16)

        shift_inner = ctk.CTkFrame(shift_card, fg_color="transparent")
        shift_inner.pack(fill="x", padx=20, pady=16)

        shift_left = ctk.CTkFrame(shift_inner, fg_color="transparent")
        shift_left.pack(side="left", fill="y")

        ctk.CTkLabel(
            shift_left,
            text="Work Shift",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        ).pack(anchor="w")

        self._shift_status_label = ctk.CTkLabel(
            shift_left,
            text="Not started",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        self._shift_status_label.pack(anchor="w")

        self._shift_btn = ctk.CTkButton(
            shift_inner,
            text="▶  Start Shift",
            width=150, height=42,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLOR_SUCCESS,
            hover_color="#1e8449",
            command=self._toggle_shift,
        )
        self._shift_btn.pack(side="right")

        # ── Stat Cards ─────────────────────────────────────────────── #
        cards_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        cards_frame.pack(fill="x", padx=24, pady=(8, 8))
        for i in range(3):
            cards_frame.columnconfigure(i, weight=1)

        self._card_total = StatCard(cards_frame, "Total Time Today", bar_color=COLOR_ACCENT)
        self._card_total.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._card_time = StatCard(cards_frame, "Active Time", bar_color=COLOR_SUCCESS)
        self._card_time.grid(row=0, column=1, sticky="ew", padx=3)

        self._card_idle = StatCard(cards_frame, "Idle Time", bar_color=COLOR_WARNING)
        self._card_idle.grid(row=0, column=2, sticky="ew", padx=(6, 0))

        # ── Hourly Chart ───────────────────────────────────────────── #
        self._chart = ActivityChart(scroll, title="Hourly Productivity (Today)")
        self._chart.pack(fill="x", padx=24, pady=(8, 8))


    # ------------------------------------------------------------------ #
    # Shift control
    # ------------------------------------------------------------------ #

    def _toggle_shift(self):
        if self._tracker is None:
            return
        self._shift_btn.configure(state="disabled")
        if self._tracker.is_running:
            self.after(50, self._do_stop_shift)
        else:
            self.after(50, self._do_start_shift)

    def _do_start_shift(self):
        def _start():
            try:
                self._tracker.start()
            except Exception:
                pass
            if self.winfo_exists():
                self.after(0, self._on_shift_changed)
        threading.Thread(target=_start, daemon=True).start()

    def _do_stop_shift(self):
        def _stop():
            try:
                self._tracker.stop()
            except Exception:
                pass
            if self.winfo_exists():
                self.after(0, self._on_shift_changed)
        threading.Thread(target=_stop, daemon=True).start()

    def _on_shift_changed(self):
        self._update_shift_ui()
        self._shift_btn.configure(state="normal")
        # Immediately kick off a DB refresh so stats reflect the change
        self._tick_counter = _DB_REFRESH_EVERY_N_TICKS

    def _update_shift_ui(self):
        if not self.winfo_exists():
            return
        if self._tracker and self._tracker.is_running:
            self._shift_btn.configure(
                text="■  End Shift",
                fg_color=COLOR_DANGER,
                hover_color="#c0392b",
            )
            self._shift_status_label.configure(
                text="● Shift active — tracking in progress",
                text_color=COLOR_SUCCESS,
            )
        else:
            self._shift_btn.configure(
                text="▶  Start Shift",
                fg_color=COLOR_SUCCESS,
                hover_color="#1e8449",
            )
            self._shift_status_label.configure(
                text="Shift not started",
                text_color=COLOR_TEXT_MUTED,
            )

    # ------------------------------------------------------------------ #
    # Two-tier refresh
    #   Tier 1 (every 5s, main thread, zero DB): time + live tracker stats
    #   Tier 2 (every 60s, background thread): DB summary, chart, screenshots
    # ------------------------------------------------------------------ #

    def _refresh(self):
        if not self.winfo_exists():
            return

        # --- Tier 1: instant, no DB, no widget rebuild ---
        self._time_label.configure(text=datetime.now().strftime("%A, %B %d  %H:%M"))
        self._update_shift_ui()

        # --- Tier 2: DB refresh every N ticks ---
        self._tick_counter += 1
        if self._tick_counter >= _DB_REFRESH_EVERY_N_TICKS and not self._refreshing:
            self._tick_counter = 0
            self._refreshing = True
            threading.Thread(target=self._fetch_data, daemon=True).start()

    # ------------------------------------------------------------------ #
    # Background DB fetch (runs every ~60s)
    # ------------------------------------------------------------------ #

    def _fetch_data(self):
        try:
            emp_id = self._session.current_user.id
            date_str = datetime.now().strftime("%Y-%m-%d")
            summary = self._storage.get_today_summary(emp_id)
            hourly = self._storage.get_hourly_scores(emp_id, date_str)
            if self.winfo_exists():
                self.after(0, lambda s=summary, h=hourly: self._apply_data(s, h))
        except Exception:
            pass
        finally:
            self._refreshing = False

    def _apply_data(self, summary, hourly):
        """Called on main thread. Only updates what actually changed."""
        if not self.winfo_exists():
            return

        active_s = summary["active_seconds"]
        idle_s = summary["idle_seconds"]
        total_s = active_s + idle_s
        self._card_total.set_value(value=_fmt_seconds(total_s))
        self._card_time.set_value(value=_fmt_seconds(active_s))
        self._card_idle.set_value(value=_fmt_seconds(idle_s))

        # Only redraw chart if data actually changed
        if hourly != self._last_hourly:
            self._last_hourly = hourly
            self._chart.set_data(hourly)

    # ------------------------------------------------------------------ #
    # Scheduler
    # ------------------------------------------------------------------ #

    def _schedule_refresh(self):
        if self.winfo_exists():
            self.after(5000, self._auto_refresh)

    def _auto_refresh(self):
        if not self.winfo_exists():
            return
        self._refresh()
        self._schedule_refresh()

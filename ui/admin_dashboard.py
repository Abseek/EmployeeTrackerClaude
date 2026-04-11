import threading
from datetime import datetime

import customtkinter as ctk

from config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_SUCCESS, COLOR_DANGER, COLOR_BORDER,
    score_color, score_label,
)
from ui.widgets.stat_card import StatCard


class AdminDashboard(ctk.CTkFrame):
    def __init__(self, master, session, storage, **kwargs):
        super().__init__(master, fg_color=COLOR_BG, corner_radius=0, **kwargs)
        self._session = session
        self._storage = storage
        self._refreshing = False
        self._tick_counter = 2  # trigger DB fetch on first _refresh() call

        self._build()
        self._refresh()
        self._schedule_refresh()

    def _build(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 0))

        ctk.CTkLabel(
            header,
            text="Admin Dashboard",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        ).pack(side="left")

        self._date_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
        )
        self._date_label.pack(side="right")

        # Stat cards row
        self._cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._cards_frame.pack(fill="x", padx=24, pady=16)
        for i in range(3):
            self._cards_frame.columnconfigure(i, weight=1)

        self._card_total = StatCard(self._cards_frame, "Total Employees", bar_color=COLOR_ACCENT)
        self._card_total.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self._card_active = StatCard(self._cards_frame, "Active Today", bar_color=COLOR_SUCCESS)
        self._card_active.grid(row=0, column=1, sticky="ew", padx=4)

        self._card_avg = StatCard(self._cards_frame, "Avg Productivity Today", bar_color=COLOR_ACCENT)
        self._card_avg.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        # Employee table header
        table_header = ctk.CTkFrame(self, fg_color="transparent")
        table_header.pack(fill="x", padx=24, pady=(4, 0))

        ctk.CTkLabel(
            table_header,
            text="Employee Overview",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        ).pack(side="left")

        # Scrollable employee table
        self._table_frame = ctk.CTkScrollableFrame(
            self, fg_color=COLOR_CARD, corner_radius=12
        )
        self._table_frame.pack(fill="both", expand=True, padx=24, pady=(8, 20))

        # Table column headers
        cols = ctk.CTkFrame(self._table_frame, fg_color="transparent")
        cols.pack(fill="x", padx=8, pady=(8, 4))

        for text, weight in [
            ("Name", 3), ("Username", 2), ("Role", 1),
            ("Today's Score", 2), ("Status", 2), ("Actions", 2),
        ]:
            ctk.CTkLabel(
                cols,
                text=text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLOR_TEXT_MUTED,
                anchor="w",
            ).pack(side="left", expand=(weight > 1), fill="x", padx=4)

        ctk.CTkFrame(self._table_frame, fg_color=COLOR_BORDER, height=1).pack(
            fill="x", padx=8, pady=4
        )

        self._rows_frame = ctk.CTkFrame(self._table_frame, fg_color="transparent")
        self._rows_frame.pack(fill="both", expand=True)

    # ------------------------------------------------------------------ #
    # Refresh — only updates date label on main thread, DB in background
    # ------------------------------------------------------------------ #

    def _refresh(self):
        if not self.winfo_exists():
            return
        self._date_label.configure(text=datetime.now().strftime("%A, %B %d, %Y"))
        self._tick_counter += 1
        if self._tick_counter >= 2 and not self._refreshing:  # every 60s (2 × 30s)
            self._tick_counter = 0
            self._refreshing = True
            threading.Thread(target=self._fetch_data, daemon=True).start()

    def _fetch_data(self):
        try:
            accounts = self._storage.get_all_accounts()
            employees = [a for a in accounts if not a.is_admin()]
            summaries = {}
            for emp in employees:
                summaries[emp.id] = self._storage.get_today_summary(emp.id)
            if self.winfo_exists():
                self.after(0, lambda e=employees, s=summaries: self._apply_data(e, s))
        except Exception:
            pass
        finally:
            self._refreshing = False

    def _apply_data(self, employees, summaries):
        if not self.winfo_exists():
            return

        active_count = 0
        total_scores = []

        for w in self._rows_frame.winfo_children():
            w.destroy()

        for emp in employees:
            summary = summaries.get(emp.id, {})
            if summary.get("is_active_today"):
                active_count += 1
            if summary.get("avg_productivity", 0) > 0:
                total_scores.append(summary["avg_productivity"])
            self._add_row(emp, summary)

        if not employees:
            ctk.CTkLabel(
                self._rows_frame,
                text="No employees yet. Add employees from the Employees tab.",
                text_color=COLOR_TEXT_MUTED,
                font=ctk.CTkFont(size=12),
            ).pack(pady=30)

        avg_score = round(sum(total_scores) / len(total_scores), 1) if total_scores else 0.0

        self._card_total.set_value(value=str(len(employees)))
        self._card_active.set_value(value=str(active_count))
        self._card_avg.set_value(
            value=f"{avg_score}%",
            bar_color=score_color(avg_score),
        )

    def _add_row(self, emp, summary):
        row = ctk.CTkFrame(self._rows_frame, fg_color="transparent", height=40)
        row.pack(fill="x", padx=8, pady=2)
        row.pack_propagate(False)

        score = summary.get("avg_productivity", 0)
        is_active = summary.get("is_active_today", False)

        def _lbl(text, color=COLOR_TEXT, weight="normal"):
            return ctk.CTkLabel(
                row, text=text,
                font=ctk.CTkFont(size=12, weight=weight),
                text_color=color, anchor="w",
            )

        _lbl(emp.display_name, weight="bold").pack(side="left", expand=True, fill="x", padx=4)
        _lbl(emp.username).pack(side="left", expand=True, fill="x", padx=4)
        _lbl(emp.role.capitalize(), COLOR_TEXT_MUTED).pack(side="left", fill="x", padx=4, ipadx=20)

        score_text = f"{score}%" if score > 0 else "—"
        _lbl(score_text, color=score_color(score)).pack(side="left", expand=True, fill="x", padx=4)

        status_color = COLOR_SUCCESS if is_active else COLOR_TEXT_MUTED
        status_text = "● Active" if is_active else "○ Offline"
        _lbl(status_text, color=status_color).pack(side="left", expand=True, fill="x", padx=4)

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.pack(side="right", padx=4)

        ctk.CTkButton(
            actions, text="Report", width=70, height=26,
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_ACCENT, hover_color="#1a5fa8",
            command=lambda e=emp: self._open_report(e),
        ).pack(side="left", padx=2)

    def _open_report(self, emp):
        try:
            self.master.master.show_content("report_viewer", employee=emp)
        except Exception:
            pass

    def _schedule_refresh(self):
        if self.winfo_exists():
            self.after(30000, self._auto_refresh)  # every 30 seconds

    def _auto_refresh(self):
        if not self.winfo_exists():
            return
        try:
            self._refresh()
        except Exception:
            pass
        self._schedule_refresh()

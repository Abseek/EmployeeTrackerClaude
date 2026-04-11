import customtkinter as ctk

from config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_SUCCESS, COLOR_DANGER, DEFAULT_SETTINGS,
)
from system.autostart import get_autostart, set_autostart


class SettingsScreen(ctk.CTkFrame):
    def __init__(self, master, session, storage, **kwargs):
        super().__init__(master, fg_color=COLOR_BG, corner_radius=0, **kwargs)
        self._session = session
        self._storage = storage
        self._settings = storage.load_settings()
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(
            scroll,
            text="Settings",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        ).pack(fill="x", padx=24, pady=(20, 16))

        # ── Screenshot Settings ──────────────────────────────────────── #
        self._section(scroll, "Screenshot Capture")

        card1 = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=12)
        card1.pack(fill="x", padx=24, pady=(0, 16))
        inner1 = ctk.CTkFrame(card1, fg_color="transparent")
        inner1.pack(padx=20, pady=16, fill="x")

        self._min_var = ctk.IntVar(value=self._settings.get("screenshot_interval_min_seconds", 300))
        self._max_var = ctk.IntVar(value=self._settings.get("screenshot_interval_max_seconds", 900))
        self._quality_var = ctk.IntVar(value=self._settings.get("screenshot_quality", 85))

        self._min_slider = self._slider_row(
            inner1, "Min Interval (seconds)",
            self._min_var, 60, 1800, self._on_min_change,
        )
        self._max_slider = self._slider_row(
            inner1, "Max Interval (seconds)",
            self._max_var, 120, 3600, self._on_max_change,
        )
        self._quality_slider = self._slider_row(
            inner1, "Screenshot Quality (PNG compression)",
            self._quality_var, 30, 100, None,
        )

        # ── Idle Detection ──────────────────────────────────────────── #
        self._section(scroll, "Idle Detection")

        card2 = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=12)
        card2.pack(fill="x", padx=24, pady=(0, 16))
        inner2 = ctk.CTkFrame(card2, fg_color="transparent")
        inner2.pack(padx=20, pady=16, fill="x")

        self._idle_var = ctk.IntVar(value=self._settings.get("idle_threshold_seconds", 60))
        self._slider_row(inner2, "Idle Threshold (seconds)", self._idle_var, 30, 300, None)

        # ── Productivity Weights ─────────────────────────────────────── #
        self._section(scroll, "Productivity Score Weights")

        card3 = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=12)
        card3.pack(fill="x", padx=24, pady=(0, 16))
        inner3 = ctk.CTkFrame(card3, fg_color="transparent")
        inner3.pack(padx=20, pady=16, fill="x")

        w = self._settings.get("productivity_weights", DEFAULT_SETTINGS["productivity_weights"])
        self._w_kb = ctk.DoubleVar(value=w.get("keyboard", 0.40))
        self._w_cl = ctk.DoubleVar(value=w.get("mouse_clicks", 0.30))
        self._w_mv = ctk.DoubleVar(value=w.get("mouse_movement", 0.20))
        self._w_sc = ctk.DoubleVar(value=w.get("mouse_scroll", 0.10))

        self._slider_row(inner3, "Keyboard Weight", self._w_kb, 0.05, 0.80, self._update_weights_sum, is_float=True)
        self._slider_row(inner3, "Mouse Clicks Weight", self._w_cl, 0.05, 0.80, self._update_weights_sum, is_float=True)
        self._slider_row(inner3, "Mouse Movement Weight", self._w_mv, 0.05, 0.80, self._update_weights_sum, is_float=True)
        self._slider_row(inner3, "Mouse Scroll Weight", self._w_sc, 0.05, 0.80, self._update_weights_sum, is_float=True)

        self._weights_sum_label = ctk.CTkLabel(
            inner3, text="",
            font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED, anchor="w",
        )
        self._weights_sum_label.pack(fill="x", pady=(4, 0))
        self._update_weights_sum()

        # ── Application ─────────────────────────────────────────────── #
        self._section(scroll, "Application")

        card4 = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=12)
        card4.pack(fill="x", padx=24, pady=(0, 16))
        inner4 = ctk.CTkFrame(card4, fg_color="transparent")
        inner4.pack(padx=20, pady=16, fill="x")

        self._autostart_var = ctk.BooleanVar(value=get_autostart())
        self._tray_var = ctk.BooleanVar(value=self._settings.get("minimize_to_tray", True))

        self._switch_row(inner4, "Start with Windows", self._autostart_var)
        self._switch_row(inner4, "Minimize to system tray on close", self._tray_var)

        # ── Buttons ─────────────────────────────────────────────────── #
        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 24))

        ctk.CTkButton(
            btn_row, text="Reset Defaults",
            width=150, height=38,
            fg_color="#333", hover_color="#444",
            command=self._reset_defaults,
        ).pack(side="left", padx=(0, 10))

        self._save_btn = ctk.CTkButton(
            btn_row, text="Save Settings",
            width=150, height=38,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            command=self._save,
        )
        self._save_btn.pack(side="left")

        self._status_label = ctk.CTkLabel(
            btn_row, text="",
            font=ctk.CTkFont(size=12), text_color=COLOR_SUCCESS,
        )
        self._status_label.pack(side="left", padx=12)

    def _section(self, parent, title: str):
        ctk.CTkLabel(
            parent, text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXT, anchor="w",
        ).pack(fill="x", padx=24, pady=(8, 4))

    def _slider_row(self, parent, label: str, var, from_, to, command, is_float=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6)

        ctk.CTkLabel(
            row, text=label, font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED, anchor="w", width=260,
        ).pack(side="left")

        val_label = ctk.CTkLabel(
            row, text=f"{var.get():.2f}" if is_float else str(int(var.get())),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT, width=50, anchor="e",
        )
        val_label.pack(side="right")

        def _on_change(val):
            if is_float:
                val_label.configure(text=f"{float(val):.2f}")
            else:
                val_label.configure(text=str(int(float(val))))
            if command:
                command()

        slider = ctk.CTkSlider(
            row, from_=from_, to=to, variable=var,
            command=_on_change, width=200,
        )
        slider.pack(side="right", padx=(0, 8))
        return slider

    def _switch_row(self, parent, label: str, var):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6)
        ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12),
                     text_color=COLOR_TEXT, anchor="w").pack(side="left")
        ctk.CTkSwitch(row, text="", variable=var).pack(side="right")

    def _on_min_change(self):
        if self._min_var.get() >= self._max_var.get():
            self._max_var.set(self._min_var.get() + 60)

    def _on_max_change(self):
        if self._max_var.get() <= self._min_var.get():
            self._min_var.set(max(60, self._max_var.get() - 60))

    def _update_weights_sum(self):
        total = self._w_kb.get() + self._w_cl.get() + self._w_mv.get() + self._w_sc.get()
        color = COLOR_SUCCESS if abs(total - 1.0) < 0.01 else COLOR_DANGER
        self._weights_sum_label.configure(
            text=f"Weights sum: {total:.2f}  (should equal 1.00)",
            text_color=color,
        )

    def _save(self):
        self._settings["screenshot_interval_min_seconds"] = int(self._min_var.get())
        self._settings["screenshot_interval_max_seconds"] = int(self._max_var.get())
        self._settings["screenshot_quality"] = int(self._quality_var.get())
        self._settings["idle_threshold_seconds"] = int(self._idle_var.get())
        self._settings["productivity_weights"] = {
            "keyboard": round(self._w_kb.get(), 2),
            "mouse_clicks": round(self._w_cl.get(), 2),
            "mouse_movement": round(self._w_mv.get(), 2),
            "mouse_scroll": round(self._w_sc.get(), 2),
        }
        self._settings["minimize_to_tray"] = self._tray_var.get()
        self._settings["autostart_enabled"] = self._autostart_var.get()
        self._storage.save_settings(self._settings)
        set_autostart(self._autostart_var.get())
        self._status_label.configure(text="✓ Saved")
        self.after(2500, lambda: self._status_label.configure(text=""))

    def _reset_defaults(self):
        from config import DEFAULT_SETTINGS
        self._settings = DEFAULT_SETTINGS.copy()
        self._storage.save_settings(self._settings)
        # Reload the screen
        for w in self.winfo_children():
            w.destroy()
        self._settings = self._storage.load_settings()
        self._build()

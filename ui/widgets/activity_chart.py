import customtkinter as ctk

from config import COLOR_CARD, COLOR_ACCENT, COLOR_TEXT_MUTED, COLOR_BORDER


class ActivityChart(ctk.CTkFrame):
    """
    Simple bar chart showing hourly productivity scores (0–100).
    Uses tkinter Canvas — no matplotlib dependency.
    """

    BAR_COLOR = COLOR_ACCENT
    BAR_ZERO_COLOR = "#1e2d4a"
    AXIS_COLOR = COLOR_BORDER
    LABEL_COLOR = COLOR_TEXT_MUTED

    def __init__(self, master, title: str = "Hourly Activity", **kwargs):
        super().__init__(master, fg_color=COLOR_CARD, corner_radius=12, **kwargs)

        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(12, 0))

        self._canvas = ctk.CTkCanvas(
            self,
            bg=COLOR_CARD,
            highlightthickness=0,
            height=120,
        )
        self._canvas.pack(fill="x", padx=16, pady=(4, 12))
        self._data: list = [0.0] * 24
        self._canvas.bind("<Configure>", self._on_resize)

    def set_data(self, hourly_scores: list):
        """Update with a list of 24 floats (0.0–100.0)."""
        if len(hourly_scores) != 24:
            return
        self._data = hourly_scores
        self._draw_chart()

    def _on_resize(self, event):
        self._draw_chart()

    def _draw_chart(self):
        canvas = self._canvas
        canvas.delete("all")

        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w <= 1 or h <= 1:
            return

        padding_left = 28
        padding_bottom = 20
        chart_w = w - padding_left - 4
        chart_h = h - padding_bottom - 4

        bar_w = chart_w / 24
        gap = max(1, bar_w * 0.15)

        # Baseline
        y_base = h - padding_bottom
        canvas.create_line(
            padding_left, y_base, w - 4, y_base,
            fill=self.AXIS_COLOR, width=1,
        )

        for i, score in enumerate(self._data):
            x0 = padding_left + i * bar_w + gap / 2
            x1 = padding_left + (i + 1) * bar_w - gap / 2
            bar_h = (score / 100.0) * chart_h

            color = self.BAR_ZERO_COLOR if score < 1 else self.BAR_COLOR
            if score >= 81:
                color = "#27ae60"
            elif score >= 61:
                color = COLOR_ACCENT
            elif score >= 31:
                color = "#f39c12"
            elif score >= 1:
                color = "#e74c3c"

            canvas.create_rectangle(
                x0, y_base - bar_h, x1, y_base,
                fill=color, outline="",
            )

            # Hour labels every 4 hours
            if i % 4 == 0:
                canvas.create_text(
                    x0 + (x1 - x0) / 2, y_base + 4,
                    text=f"{i:02d}",
                    fill=self.LABEL_COLOR,
                    font=("Segoe UI", 8),
                    anchor="n",
                )

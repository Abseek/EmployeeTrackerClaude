import customtkinter as ctk

from config import COLOR_CARD, COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_ACCENT


class StatCard(ctk.CTkFrame):
    """Reusable metric card: large value, title, optional subtitle and color bar."""

    def __init__(self, master, title: str, value: str = "—",
                 subtitle: str = "", bar_color: str = COLOR_ACCENT, **kwargs):
        super().__init__(
            master,
            fg_color=COLOR_CARD,
            corner_radius=12,
            **kwargs,
        )

        self._bar_color = bar_color

        # Color accent bar at top
        self._bar = ctk.CTkFrame(self, height=4, fg_color=bar_color, corner_radius=2)
        self._bar.pack(fill="x", padx=0, pady=(0, 0))

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)

        self._title_label = ctk.CTkLabel(
            inner,
            text=title,
            font=ctk.CTkFont(size=11, weight="normal"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        self._title_label.pack(fill="x")

        self._value_label = ctk.CTkLabel(
            inner,
            text=value,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        )
        self._value_label.pack(fill="x")

        self._subtitle_label = ctk.CTkLabel(
            inner,
            text=subtitle,
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        self._subtitle_label.pack(fill="x")

    def set_value(self, value: str = None, subtitle: str = None, bar_color: str = None):
        if value is not None:
            self._value_label.configure(text=value)
        if subtitle is not None:
            self._subtitle_label.configure(text=subtitle)
        if bar_color is not None:
            self._bar.configure(fg_color=bar_color)

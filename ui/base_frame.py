import customtkinter as ctk

from config import (
    COLOR_SIDEBAR, COLOR_SIDEBAR_BTN, COLOR_SIDEBAR_ACTIVE,
    COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_ACCENT,
)


NAV_ITEMS_ADMIN = [
    ("dashboard",      "📊  Dashboard"),
    ("account_manager","👥  Employees"),
    ("report_viewer",  "📋  Reports"),
    ("settings_screen","⚙️  Settings"),
]

NAV_ITEMS_EMPLOYEE = [
    ("employee_dashboard", "📊  Dashboard"),
]


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, session, on_navigate, on_logout, **kwargs):
        super().__init__(
            master,
            fg_color=COLOR_SIDEBAR,
            corner_radius=0,
            width=220,
            **kwargs,
        )
        self.pack_propagate(False)

        self._on_navigate = on_navigate
        self._on_logout = on_logout
        self._buttons: dict = {}
        self._active_screen = ""

        # App logo / title
        logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        logo_frame.pack(fill="x", padx=16, pady=(20, 8))

        ctk.CTkLabel(
            logo_frame,
            text="⏱",
            font=ctk.CTkFont(size=28),
            text_color=COLOR_ACCENT,
        ).pack(side="left")

        ctk.CTkLabel(
            logo_frame,
            text="  Tracker",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left")

        # Divider
        ctk.CTkFrame(self, fg_color=COLOR_ACCENT, height=2).pack(
            fill="x", padx=16, pady=(4, 16)
        )

        # Navigation buttons
        nav_items = NAV_ITEMS_ADMIN if session.is_admin() else NAV_ITEMS_EMPLOYEE
        for screen_key, label in nav_items:
            btn = ctk.CTkButton(
                self,
                text=label,
                anchor="w",
                fg_color="transparent",
                hover_color=COLOR_SIDEBAR_BTN,
                text_color=COLOR_TEXT,
                font=ctk.CTkFont(size=13),
                height=38,
                corner_radius=8,
                command=lambda k=screen_key: self._navigate(k),
            )
            btn.pack(fill="x", padx=8, pady=2)
            self._buttons[screen_key] = btn

        # Spacer
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        # User info at bottom
        ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR_BTN, height=1).pack(fill="x", padx=16, pady=4)

        user_frame = ctk.CTkFrame(self, fg_color="transparent")
        user_frame.pack(fill="x", padx=12, pady=(4, 4))

        display_name = session.current_user.display_name if session.current_user else ""
        role = session.current_user.role.capitalize() if session.current_user else ""

        ctk.CTkLabel(
            user_frame,
            text=display_name,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            user_frame,
            text=role,
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x")

        ctk.CTkButton(
            self,
            text="⏏  Logout",
            fg_color="transparent",
            hover_color="#3a1a1a",
            text_color="#e74c3c",
            font=ctk.CTkFont(size=12),
            height=34,
            corner_radius=8,
            command=on_logout,
        ).pack(fill="x", padx=8, pady=(4, 16))

    def set_active(self, screen_key: str):
        if self._active_screen and self._active_screen in self._buttons:
            self._buttons[self._active_screen].configure(fg_color="transparent")
        self._active_screen = screen_key
        if screen_key in self._buttons:
            self._buttons[screen_key].configure(fg_color=COLOR_SIDEBAR_ACTIVE)

    def _navigate(self, screen_key: str):
        self._on_navigate(screen_key)

import os
import customtkinter as ctk

from config import (
    APP_NAME, WINDOW_SIZE, WINDOW_MIN, WINDOW_TITLE,
    COLOR_BG, ICON_ICO, ICON_PNG,
)
from data.storage import Storage
from data.session_manager import SessionManager
from system.tray_icon import TrayIcon
from ui.login_screen import LoginScreen
from ui.base_frame import Sidebar


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class EmployeeTrackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(WINDOW_TITLE)
        self.geometry(WINDOW_SIZE)
        self.minsize(*WINDOW_MIN)
        self.configure(fg_color=COLOR_BG)

        # Set window icon
        try:
            if ICON_ICO.exists():
                self.iconbitmap(str(ICON_ICO))
        except Exception:
            pass

        # Core services
        self.storage = Storage()
        self.session = SessionManager(self.storage)
        self.tracker = None
        self.tray = TrayIcon(self)

        # Layout references
        self._sidebar = None
        self._content_frame = None

        # First run: create default admin account
        self._first_run = self.storage.is_first_run()
        if self._first_run:
            self.session.create_default_admin()

        # Protocol
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Show login screen
        self._show_login()

        # Show first-run dialog after mainloop starts
        if self._first_run:
            self.after(400, self._show_first_run_dialog)

    # ------------------------------------------------------------------ #
    # Screen management
    # ------------------------------------------------------------------ #

    def _show_login(self):
        self._clear_window()
        login = LoginScreen(
            self, self.session, self.storage,
            on_success=self._on_login_success,
        )
        login.pack(fill="both", expand=True)

    def _on_login_success(self):
        self._clear_window()
        self._build_main_layout()

        if self.session.is_admin():
            self.show_content("dashboard")
        else:
            # Start tracker for employee — delay to let Tkinter message loop run
            settings = self.storage.load_settings()
            from core.tracker import Tracker
            self.tracker = Tracker(
                self.session.current_user.id, settings, self.storage
            )
            self.show_content("employee_dashboard")

    def _build_main_layout(self):
        self._sidebar = Sidebar(
            self,
            self.session,
            on_navigate=self.show_content,
            on_logout=self._on_logout,
        )
        self._sidebar.pack(side="left", fill="y")

        self._content_frame = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self._content_frame.pack(side="left", fill="both", expand=True)

    def show_content(self, screen_name: str, **kwargs):
        """Switch the right-side content area."""
        ADMIN_ONLY = {"account_manager", "settings_screen"}
        if screen_name in ADMIN_ONLY and not self.session.is_admin():
            return

        if self._content_frame is None:
            return

        for w in self._content_frame.winfo_children():
            w.destroy()

        screen = self._create_screen(screen_name, **kwargs)
        if screen:
            screen.pack(fill="both", expand=True)
            if self._sidebar:
                self._sidebar.set_active(screen_name)

    def _create_screen(self, name: str, **kwargs):
        from ui.admin_dashboard import AdminDashboard
        from ui.employee_dashboard import EmployeeDashboard
        from ui.account_manager import AccountManager
        from ui.settings_screen import SettingsScreen
        from ui.report_viewer import ReportViewer

        if name == "dashboard":
            return AdminDashboard(self._content_frame, self.session, self.storage)
        elif name == "employee_dashboard":
            return EmployeeDashboard(
                self._content_frame, self.session, self.storage, self.tracker
            )
        elif name == "account_manager":
            return AccountManager(self._content_frame, self.session, self.storage)
        elif name == "settings_screen":
            return SettingsScreen(self._content_frame, self.session, self.storage)
        elif name == "report_viewer":
            employee = kwargs.get("employee")
            return ReportViewer(
                self._content_frame, self.session, self.storage, employee=employee
            )
        return None

    def _on_logout(self):
        if self.tracker:
            self.tracker.stop()
            self.tracker = None
        self.session.logout()
        self._clear_window()
        self._show_login()

    def _clear_window(self):
        for w in self.winfo_children():
            w.destroy()
        self._sidebar = None
        self._content_frame = None

    # ------------------------------------------------------------------ #
    # Window close / tray
    # ------------------------------------------------------------------ #

    def _on_close(self):
        # Only minimize to tray when a shift is actively running — tracking must continue.
        # In every other case (no shift, not logged in), just quit cleanly.
        tracker_running = self.tracker is not None and self.tracker.is_running
        if tracker_running:
            self.withdraw()
            if not self.tray._icon:
                self.tray.start()
        else:
            self.quit_app()

    def quit_app(self):
        # Stop tracker synchronously so the final bucket + session end are written
        if self.tracker:
            try:
                self.tracker.stop()
            except Exception:
                pass
        try:
            self.tray.stop()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        # Force-kill the process. Without this, MySQL connection pool threads
        # (non-daemon) keep the process alive indefinitely after the window closes.
        os._exit(0)

    # ------------------------------------------------------------------ #
    # First-run dialog
    # ------------------------------------------------------------------ #

    def _show_first_run_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Welcome to Employee Tracker")
        dlg.geometry("420x280")
        dlg.resizable(False, False)
        dlg.configure(fg_color="#1a1a2e")
        dlg.after(50, dlg.lift)
        dlg.grab_set()

        inner = ctk.CTkFrame(dlg, fg_color="transparent")
        inner.pack(padx=30, pady=30, fill="both", expand=True)

        ctk.CTkLabel(
            inner, text="🎉  First Time Setup",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#e0e0e0",
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            inner,
            text="A default admin account has been created.\nPlease sign in and change the password immediately.",
            font=ctk.CTkFont(size=12),
            text_color="#8899aa",
            wraplength=360,
            justify="center",
        ).pack()

        cred_frame = ctk.CTkFrame(inner, fg_color="#0f3460", corner_radius=8)
        cred_frame.pack(fill="x", pady=16)

        for label, value in [("Username", "admin"), ("Password", "Admin123!")]:
            row = ctk.CTkFrame(cred_frame, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(row, text=label + ":", font=ctk.CTkFont(size=12),
                         text_color="#8899aa", width=80, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, font=ctk.CTkFont(size=13, weight="bold"),
                         text_color="#2D7DD2").pack(side="left")

        ctk.CTkButton(
            inner, text="Got it",
            fg_color="#2D7DD2", hover_color="#1a5fa8",
            command=dlg.destroy,
        ).pack(fill="x", pady=(4, 0))

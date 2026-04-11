import customtkinter as ctk

from config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_DANGER,
)


class LoginScreen(ctk.CTkFrame):
    def __init__(self, master, session, storage, on_success, **kwargs):
        super().__init__(master, fg_color=COLOR_BG, corner_radius=0, **kwargs)
        self._session = session
        self._storage = storage
        self._on_success = on_success

        # Center the card
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=16, width=400)
        card.grid(row=0, column=0, sticky="")
        card.grid_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=40, fill="both", expand=True)

        # Logo + title
        ctk.CTkLabel(
            inner,
            text="⏱",
            font=ctk.CTkFont(size=48),
            text_color=COLOR_ACCENT,
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            inner,
            text="Employee Tracker",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack()

        ctk.CTkLabel(
            inner,
            text="Sign in to your account",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
        ).pack(pady=(4, 24))

        # Username
        ctk.CTkLabel(
            inner, text="Username",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x")

        self._username_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Enter username",
            height=40,
            font=ctk.CTkFont(size=13),
        )
        self._username_entry.pack(fill="x", pady=(4, 12))

        # Password
        ctk.CTkLabel(
            inner, text="Password",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x")

        self._password_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Enter password",
            show="*",
            height=40,
            font=ctk.CTkFont(size=13),
        )
        self._password_entry.pack(fill="x", pady=(4, 4))

        # Error label (hidden by default)
        self._error_label = ctk.CTkLabel(
            inner,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_DANGER,
            anchor="w",
        )
        self._error_label.pack(fill="x", pady=(0, 12))

        # Login button
        self._login_btn = ctk.CTkButton(
            inner,
            text="Login",
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            command=self._attempt_login,
        )
        self._login_btn.pack(fill="x")

        # Bind Enter key
        self._username_entry.bind("<Return>", lambda e: self._attempt_login())
        self._password_entry.bind("<Return>", lambda e: self._attempt_login())

        # Focus username
        self.after(100, self._username_entry.focus)

    def _attempt_login(self):
        username = self._username_entry.get().strip()
        password = self._password_entry.get()

        if not username or not password:
            self._error_label.configure(text="Please enter username and password.")
            return

        self._login_btn.configure(state="disabled", text="Signing in…")
        self._error_label.configure(text="")

        success, message = self._session.login(username, password)
        if success:
            self._on_success()
        else:
            self._error_label.configure(text=message)
            self._login_btn.configure(state="normal", text="Login")
            self._password_entry.delete(0, "end")
            self._password_entry.focus()

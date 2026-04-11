import uuid
from datetime import datetime

import customtkinter as ctk

from config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_DANGER, COLOR_BORDER, COLOR_SUCCESS,
)
from data.models import Employee
from data.session_manager import hash_password


class AccountManager(ctk.CTkFrame):
    def __init__(self, master, session, storage, **kwargs):
        super().__init__(master, fg_color=COLOR_BG, corner_radius=0, **kwargs)
        self._session = session
        self._storage = storage
        self._build()
        self._load_accounts()

    def _build(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 0))

        ctk.CTkLabel(
            header,
            text="Employee Accounts",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="+ Add Employee",
            width=140,
            height=36,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._open_add_modal,
        ).pack(side="right")

        # Table
        self._table = ctk.CTkScrollableFrame(
            self, fg_color=COLOR_CARD, corner_radius=12
        )
        self._table.pack(fill="both", expand=True, padx=24, pady=16)

        # Column headers
        hdr = ctk.CTkFrame(self._table, fg_color="transparent")
        hdr.pack(fill="x", padx=8, pady=(8, 4))
        for text in ["Name", "Username", "Email", "Role", "Status", "Actions"]:
            ctk.CTkLabel(
                hdr, text=text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLOR_TEXT_MUTED,
                anchor="w",
            ).pack(side="left", expand=True, fill="x", padx=4)

        ctk.CTkFrame(self._table, fg_color=COLOR_BORDER, height=1).pack(
            fill="x", padx=8, pady=4
        )
        self._rows_container = ctk.CTkFrame(self._table, fg_color="transparent")
        self._rows_container.pack(fill="both", expand=True)

    def _load_accounts(self):
        for w in self._rows_container.winfo_children():
            w.destroy()
        accounts = self._storage.get_all_accounts()
        if not accounts:
            ctk.CTkLabel(
                self._rows_container,
                text="No accounts found.",
                text_color=COLOR_TEXT_MUTED,
            ).pack(pady=20)
            return
        for acc in accounts:
            self._add_row(acc)

    def _add_row(self, emp: Employee):
        row = ctk.CTkFrame(self._rows_container, fg_color="transparent", height=42)
        row.pack(fill="x", padx=8, pady=2)
        row.pack_propagate(False)

        def _lbl(text, color=COLOR_TEXT):
            return ctk.CTkLabel(
                row, text=text,
                font=ctk.CTkFont(size=12),
                text_color=color, anchor="w",
            )

        _lbl(emp.display_name).pack(
            side="left", expand=True, fill="x", padx=4
        )
        _lbl(emp.username).pack(side="left", expand=True, fill="x", padx=4)
        _lbl(emp.email, COLOR_TEXT_MUTED).pack(side="left", expand=True, fill="x", padx=4)

        role_color = COLOR_ACCENT if emp.role == "admin" else COLOR_TEXT_MUTED
        _lbl(emp.role.capitalize(), role_color).pack(side="left", fill="x", padx=4, ipadx=30)

        status_text = "Active" if emp.is_active else "Disabled"
        status_color = COLOR_SUCCESS if emp.is_active else COLOR_DANGER
        _lbl(status_text, status_color).pack(side="left", expand=True, fill="x", padx=4)

        # Actions
        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.pack(side="right", padx=4)

        ctk.CTkButton(
            actions, text="Edit", width=60, height=28,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            font=ctk.CTkFont(size=11),
            command=lambda e=emp: self._open_edit_modal(e),
        ).pack(side="left", padx=2)

        # Don't allow deleting own account
        is_self = emp.id == self._session.current_user.id
        ctk.CTkButton(
            actions, text="Delete", width=60, height=28,
            fg_color=COLOR_DANGER if not is_self else "#333",
            hover_color="#c0392b" if not is_self else "#333",
            font=ctk.CTkFont(size=11),
            state="normal" if not is_self else "disabled",
            command=lambda e=emp: self._confirm_delete(e),
        ).pack(side="left", padx=2)

    def _open_add_modal(self):
        AccountFormModal(self, self._storage, self._session, on_save=self._load_accounts)

    def _open_edit_modal(self, emp: Employee):
        AccountFormModal(
            self, self._storage, self._session,
            employee=emp, on_save=self._load_accounts
        )

    def _confirm_delete(self, emp: Employee):
        dlg = ConfirmDialog(
            self,
            title="Delete Account",
            message=f"Delete account for '{emp.display_name}' ({emp.username})?\n\nThis cannot be undone.",
            on_confirm=lambda: self._do_delete(emp),
        )
        dlg.grab_set()

    def _do_delete(self, emp: Employee):
        self._storage.delete_account(emp.id)
        self._load_accounts()


class AccountFormModal(ctk.CTkToplevel):
    def __init__(self, master, storage, session, employee=None, on_save=None, **kwargs):
        super().__init__(master, **kwargs)
        self._storage = storage
        self._session = session
        self._employee = employee
        self._on_save = on_save
        self._is_edit = employee is not None

        title = "Edit Employee" if self._is_edit else "Add Employee"
        self.title(title)
        self.geometry("460x560")
        self.resizable(False, False)
        self.configure(fg_color="#1a1a2e")
        self.after(50, self.lift)

        self._build()
        if self._is_edit:
            self._populate()

    def _build(self):
        # Fixed title at the top
        ctk.CTkLabel(
            self,
            text="Edit Employee" if self._is_edit else "Add New Employee",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        ).pack(fill="x", padx=30, pady=(24, 8))

        # Scrollable fields area — expands to fill available space
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=30, pady=0)

        def _field(label, placeholder, show=""):
            ctk.CTkLabel(scroll, text=label, font=ctk.CTkFont(size=12),
                         text_color=COLOR_TEXT_MUTED, anchor="w").pack(fill="x")
            e = ctk.CTkEntry(scroll, placeholder_text=placeholder,
                             height=38, show=show)
            e.pack(fill="x", pady=(4, 10))
            return e

        self._name_entry = _field("Display Name *", "Full name")
        self._username_entry = _field("Username *", "username (no spaces)")
        self._email_entry = _field("Email", "email@company.com")

        # Role
        ctk.CTkLabel(scroll, text="Role *", font=ctk.CTkFont(size=12),
                     text_color=COLOR_TEXT_MUTED, anchor="w").pack(fill="x")
        self._role_var = ctk.StringVar(value="employee")
        role_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        role_frame.pack(fill="x", pady=(4, 10))
        ctk.CTkRadioButton(role_frame, text="Employee", variable=self._role_var,
                           value="employee").pack(side="left", padx=(0, 16))
        ctk.CTkRadioButton(role_frame, text="Admin", variable=self._role_var,
                           value="admin").pack(side="left")

        pw_label = "New Password (leave blank to keep)" if self._is_edit else "Password *"
        self._pw_entry = _field(pw_label, "Min 6 characters", show="*")
        self._pw2_entry = _field("Confirm Password", "Repeat password", show="*")

        # Active toggle (edit only)
        if self._is_edit:
            self._active_var = ctk.BooleanVar(value=True)
            ctk.CTkCheckBox(scroll, text="Account Active",
                            variable=self._active_var).pack(anchor="w", pady=(0, 10))

        self._err_label = ctk.CTkLabel(scroll, text="", text_color=COLOR_DANGER,
                                       font=ctk.CTkFont(size=11), anchor="w")
        self._err_label.pack(fill="x")

        # Fixed buttons always visible at the bottom
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=30, pady=16)
        ctk.CTkButton(btns, text="Cancel", fg_color="#333", hover_color="#444",
                      command=self.destroy).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(btns, text="Save", fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                      command=self._save).pack(side="left", expand=True, fill="x")

    def _populate(self):
        emp = self._employee
        self._name_entry.insert(0, emp.display_name)
        self._username_entry.insert(0, emp.username)
        self._email_entry.insert(0, emp.email)
        self._role_var.set(emp.role)
        if hasattr(self, "_active_var"):
            self._active_var.set(emp.is_active)

    def _save(self):
        name = self._name_entry.get().strip()
        username = self._username_entry.get().strip()
        email = self._email_entry.get().strip()
        role = self._role_var.get()
        pw = self._pw_entry.get()
        pw2 = self._pw2_entry.get()

        # Validation
        if not name:
            return self._err("Display name is required.")
        if not username or " " in username:
            return self._err("Username is required and must not contain spaces.")
        if self._storage.username_exists(username, exclude_id=self._employee.id if self._is_edit else ""):
            return self._err("Username already exists.")
        if not self._is_edit and not pw:
            return self._err("Password is required.")
        if pw and len(pw) < 6:
            return self._err("Password must be at least 6 characters.")
        if pw and pw != pw2:
            return self._err("Passwords do not match.")

        now = datetime.now().isoformat(timespec="seconds")

        if self._is_edit:
            emp = self._employee
            emp.display_name = name
            emp.username = username
            emp.email = email
            emp.role = role
            emp.updated_at = now
            emp.is_active = self._active_var.get() if hasattr(self, "_active_var") else emp.is_active
            if pw:
                emp.password_hash = hash_password(pw)
            self._storage.update_account(emp)
        else:
            emp = Employee(
                id="emp_" + uuid.uuid4().hex[:8],
                username=username,
                display_name=name,
                email=email,
                role=role,
                password_hash=hash_password(pw),
                created_at=now,
                updated_at=now,
                is_active=True,
            )
            self._storage.create_account(emp)

        if self._on_save:
            self._on_save()
        self.destroy()

    def _err(self, msg: str):
        self._err_label.configure(text=msg)


class ConfirmDialog(ctk.CTkToplevel):
    def __init__(self, master, title: str, message: str, on_confirm, **kwargs):
        super().__init__(master, **kwargs)
        self.title(title)
        self.geometry("380x200")
        self.resizable(False, False)
        self.configure(fg_color="#1a1a2e")
        self.after(50, self.lift)
        self._on_confirm = on_confirm

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(padx=24, pady=24, fill="both", expand=True)

        ctk.CTkLabel(inner, text=message,
                     font=ctk.CTkFont(size=12),
                     text_color=COLOR_TEXT,
                     wraplength=320).pack(pady=(0, 20))

        btns = ctk.CTkFrame(inner, fg_color="transparent")
        btns.pack(fill="x")
        ctk.CTkButton(btns, text="Cancel", fg_color="#333", hover_color="#444",
                      command=self.destroy).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(btns, text="Delete", fg_color=COLOR_DANGER, hover_color="#c0392b",
                      command=self._confirm).pack(side="left", expand=True, fill="x")

    def _confirm(self):
        self._on_confirm()
        self.destroy()

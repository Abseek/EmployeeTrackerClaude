import uuid
from datetime import datetime
from typing import Optional

import bcrypt
import requests

from data.models import Employee


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


class SessionManager:
    def __init__(self, storage):
        self._storage = storage
        self.current_user: Optional[Employee] = None
        self.session_id: Optional[str] = None

    def login(self, username: str, password: str) -> tuple:
        """Returns (success: bool, message: str). bcrypt check runs server-side in Lambda."""
        try:
            account = self._storage.authenticate(username, password)
            self.current_user = account
            self.session_id = "sess_" + uuid.uuid4().hex[:8]
            return True, "OK"
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status in (401, 403):
                try:
                    msg = e.response.json().get("error", "Authentication failed.")
                except Exception:
                    msg = "Authentication failed."
                return False, msg
            return False, "Cannot connect to server. Check your internet connection."
        except Exception:
            return False, "Cannot connect to server. Check your internet connection."

    def logout(self) -> None:
        self.current_user = None
        self.session_id = None

    def is_authenticated(self) -> bool:
        return self.current_user is not None

    def is_admin(self) -> bool:
        return self.current_user is not None and self.current_user.is_admin()

    def create_default_admin(self) -> None:
        """Create the default admin account on first run."""
        from data.models import Employee
        now = datetime.now().isoformat(timespec="seconds")
        admin = Employee(
            id="emp_" + uuid.uuid4().hex[:8],
            username="admin",
            display_name="Administrator",
            email="admin@company.com",
            role="admin",
            password_hash=hash_password("Admin123!"),
            created_at=now,
            updated_at=now,
            is_active=True,
        )
        self._storage.create_account(admin)

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from config import API_ENDPOINT, API_KEY, DATA_DIR, DEFAULT_SETTINGS, LOGS_DIR
from data.models import Employee


def _to_iso(val) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat(timespec="seconds")
    return str(val)


class Storage:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update({
            "x-api-key": API_KEY,
            "Content-Type": "application/json",
        })

    # ------------------------------------------------------------------ #
    # Internal HTTP helpers
    # ------------------------------------------------------------------ #

    def _post(self, path: str, payload: dict, retries: int = 3) -> dict:
        url = f"{API_ENDPOINT}{path}"
        delay = 1.0
        last_err = None
        for attempt in range(retries):
            try:
                resp = self._session.post(url, json=payload, timeout=(5, 30))
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.HTTPError:
                raise
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    time.sleep(delay)
                    delay *= 2
        raise last_err

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{API_ENDPOINT}{path}"
        resp = self._session.get(url, params=params, timeout=(5, 30))
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, payload: dict) -> dict:
        url = f"{API_ENDPOINT}{path}"
        resp = self._session.put(url, json=payload, timeout=(5, 30))
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str) -> dict:
        url = f"{API_ENDPOINT}{path}"
        resp = self._session.delete(url, timeout=(5, 30))
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _row_to_employee(row: dict) -> Employee:
        return Employee(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            email=row.get("email", ""),
            role=row["role"],
            password_hash=row["password_hash"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_active=bool(row["is_active"]),
        )

    # ------------------------------------------------------------------ #
    # Accounts
    # ------------------------------------------------------------------ #

    def is_first_run(self) -> bool:
        return self._get("/tracker/is_first_run")["is_first_run"]

    def authenticate(self, username: str, password: str) -> Employee:
        """Returns Employee on success; raises requests.HTTPError (401/403) on failure."""
        data = self._post("/tracker/authenticate", {"username": username, "password": password})
        return self._row_to_employee(data["account"])

    def find_account_by_username(self, username: str) -> Optional[Employee]:
        data = self._get("/tracker/accounts", {"username": username})
        row = data.get("account")
        return self._row_to_employee(row) if row else None

    def find_account_by_id(self, emp_id: str) -> Optional[Employee]:
        data = self._get(f"/tracker/accounts/{emp_id}")
        row = data.get("account")
        return self._row_to_employee(row) if row else None

    def get_all_accounts(self) -> list:
        data = self._get("/tracker/accounts")
        return [self._row_to_employee(r) for r in data["accounts"]]

    def create_account(self, employee: Employee) -> None:
        self._post("/tracker/accounts", {
            "id": employee.id,
            "username": employee.username,
            "display_name": employee.display_name,
            "email": employee.email,
            "role": employee.role,
            "password_hash": employee.password_hash,
            "created_at": employee.created_at,
            "updated_at": employee.updated_at,
            "is_active": employee.is_active,
        })

    def update_account(self, employee: Employee) -> bool:
        data = self._put(f"/tracker/accounts/{employee.id}", {
            "username": employee.username,
            "display_name": employee.display_name,
            "email": employee.email,
            "role": employee.role,
            "password_hash": employee.password_hash,
            "updated_at": employee.updated_at,
            "is_active": employee.is_active,
        })
        return data.get("updated", False)

    def delete_account(self, emp_id: str) -> bool:
        data = self._delete(f"/tracker/accounts/{emp_id}")
        return data.get("deleted", False)

    def username_exists(self, username: str, exclude_id: str = "") -> bool:
        data = self._get("/tracker/accounts/check-username", {
            "username": username,
            "exclude_id": exclude_id,
        })
        return data["exists"]

    # ------------------------------------------------------------------ #
    # Settings
    # ------------------------------------------------------------------ #

    def load_settings(self) -> dict:
        try:
            data = self._get("/tracker/settings")
            loaded = data.get("settings", {})
            merged = DEFAULT_SETTINGS.copy()
            merged.update(loaded)
            return merged
        except Exception:
            return DEFAULT_SETTINGS.copy()

    def save_settings(self, settings: dict) -> None:
        self._post("/tracker/settings", {"settings": settings})

    # ------------------------------------------------------------------ #
    # Screenshot directory (files still stored locally)
    # ------------------------------------------------------------------ #

    def get_screenshots_dir(self, date_str: str) -> Path:
        p = LOGS_DIR / date_str / "screenshots"
        p.mkdir(parents=True, exist_ok=True)
        return p

    # ------------------------------------------------------------------ #
    # Sessions
    # ------------------------------------------------------------------ #

    def start_session(self, employee_id: str) -> str:
        data = self._post("/tracker/sessions/start", {"employee_id": employee_id})
        return data["session_id"]

    def end_session(self, employee_id: str, session_id: str) -> None:
        self._post("/tracker/sessions/end", {
            "employee_id": employee_id,
            "session_id": session_id,
        })

    # ------------------------------------------------------------------ #
    # Activity buckets
    # ------------------------------------------------------------------ #

    def append_bucket(self, employee_id: str, session_id: str, bucket_dict: dict) -> None:
        self._post("/tracker/buckets", {
            "employee_id": employee_id,
            "session_id": session_id,
            "bucket": bucket_dict,
        })

    def add_screenshot_record(self, employee_id: str, session_id: str, record: dict) -> None:
        self._post("/tracker/screenshots", {
            "employee_id": employee_id,
            "session_id": session_id,
            "record": record,
        })

    # ------------------------------------------------------------------ #
    # Query helpers
    # ------------------------------------------------------------------ #

    def get_today_summary(self, employee_id: str) -> dict:
        return self._get("/tracker/activity/today", {"employee_id": employee_id})

    def get_hourly_scores(self, employee_id: str, date_str: str) -> list:
        data = self._get("/tracker/activity/hourly", {
            "employee_id": employee_id,
            "date_str": date_str,
        })
        return data["hourly"]

    def load_activity(self, employee_id: str, date_str: str) -> dict:
        return self._get("/tracker/activity", {
            "employee_id": employee_id,
            "date_str": date_str,
        })

    def get_all_screenshots_for_date(self, employee_id: str, date_str: str) -> list:
        data = self._get("/tracker/activity/screenshots", {
            "employee_id": employee_id,
            "date_str": date_str,
        })
        screenshots_dir = LOGS_DIR / date_str / "screenshots"
        items = []
        for entry in data["screenshots"]:
            filename = entry["filename"]
            ftp_url = entry.get("ftp_url")
            p = screenshots_dir / filename
            if p.exists():
                items.append(p)
            elif ftp_url:
                items.append(ftp_url)
            else:
                items.append(None)
        return items

    def get_all_activity_dates(self, employee_id: str) -> list:
        data = self._get("/tracker/activity/dates", {"employee_id": employee_id})
        return data["dates"]

    @staticmethod
    def _compute_summary(buckets: list, screenshots_count: int, session_duration_seconds: int = 0) -> dict:
        if not buckets:
            return {
                "total_keystrokes": 0, "total_clicks": 0,
                "total_scroll_ticks": 0, "total_mouse_distance_px": 0.0,
                "total_active_seconds": 0, "total_idle_seconds": 0,
                "screenshots_count": screenshots_count,
                "average_productivity_score": 0.0,
            }
        BUCKET_SECONDS = 300
        total_idle = sum(min(b["idle_seconds"], BUCKET_SECONDS) for b in buckets)
        active_seconds = max(0, session_duration_seconds - total_idle)
        scores = [b["productivity_score"] for b in buckets]
        return {
            "total_keystrokes":           sum(b["keystrokes"]         for b in buckets),
            "total_clicks":               sum(b["mouse_clicks"]        for b in buckets),
            "total_scroll_ticks":         sum(b["mouse_scroll_ticks"]  for b in buckets),
            "total_mouse_distance_px":    sum(b["mouse_distance_px"]   for b in buckets),
            "total_active_seconds":       active_seconds,
            "total_idle_seconds":         total_idle,
            "screenshots_count":          screenshots_count,
            "average_productivity_score": round(sum(scores) / len(scores), 1),
        }

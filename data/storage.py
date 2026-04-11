import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import mysql.connector
from mysql.connector import pooling, Error as MySQLError

from config import (
    DATA_DIR, DEFAULT_SETTINGS, LOGS_DIR,
    DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT,
)
from data.models import Employee


def _to_iso(val) -> Optional[str]:
    """Convert a datetime or None to ISO string; pass strings through."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat(timespec="seconds")
    return str(val)


def _to_dt(val) -> Optional[datetime]:
    """Convert an ISO string or datetime to datetime; return None for None."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(val)


class Storage:
    def __init__(self):
        # Screenshots are still stored as local files; keep dirs available.
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        try:
            self._pool = pooling.MySQLConnectionPool(
                pool_name="tracker_pool",
                pool_size=5,
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                port=DB_PORT,
                autocommit=True,
                connection_timeout=10,
                use_pure=True,
            )
        except MySQLError as e:
            raise RuntimeError(
                f"Cannot connect to the database.\n"
                f"Host: {DB_HOST}  DB: {DB_NAME}\n"
                f"Error: {e}\n\n"
                "Check your internet connection and that the database server is reachable."
            ) from e

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _execute(self, query: str, params=None, fetch=None, dictionary=False):
        """
        Run a single SQL statement.
        fetch=None  → fire-and-forget (INSERT/UPDATE/DELETE), returns rowcount
        fetch="one" → fetchone() — dict if dictionary=True, else tuple
        fetch="all" → fetchall()
        """
        conn = self._pool.get_connection()
        try:
            cur = conn.cursor(dictionary=dictionary)
            cur.execute(query, params or ())
            if fetch == "one":
                return cur.fetchone()
            if fetch == "all":
                return cur.fetchall()
            return cur.rowcount
        finally:
            conn.close()  # returns connection to pool

    @staticmethod
    def _row_to_employee(row: dict) -> Employee:
        return Employee(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            email=row.get("email", ""),
            role=row["role"],
            password_hash=row["password_hash"],
            created_at=_to_iso(row["created_at"]),
            updated_at=_to_iso(row["updated_at"]),
            is_active=bool(row["is_active"]),
        )

    # ------------------------------------------------------------------ #
    # Accounts
    # ------------------------------------------------------------------ #

    def is_first_run(self) -> bool:
        row = self._execute("SELECT COUNT(*) FROM accounts", fetch="one")
        return row[0] == 0

    def find_account_by_username(self, username: str) -> Optional[Employee]:
        row = self._execute(
            "SELECT * FROM accounts WHERE LOWER(username) = LOWER(%s)",
            (username,), fetch="one", dictionary=True,
        )
        return self._row_to_employee(row) if row else None

    def find_account_by_id(self, emp_id: str) -> Optional[Employee]:
        row = self._execute(
            "SELECT * FROM accounts WHERE id = %s",
            (emp_id,), fetch="one", dictionary=True,
        )
        return self._row_to_employee(row) if row else None

    def get_all_accounts(self) -> list:
        rows = self._execute(
            "SELECT * FROM accounts ORDER BY display_name",
            fetch="all", dictionary=True,
        )
        return [self._row_to_employee(r) for r in rows]

    def create_account(self, employee: Employee) -> None:
        self._execute(
            """INSERT INTO accounts
               (id, username, display_name, email, role, password_hash,
                created_at, updated_at, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                employee.id, employee.username, employee.display_name,
                employee.email, employee.role, employee.password_hash,
                _to_dt(employee.created_at), _to_dt(employee.updated_at),
                int(employee.is_active),
            ),
        )

    def update_account(self, employee: Employee) -> bool:
        count = self._execute(
            """UPDATE accounts
               SET username=%s, display_name=%s, email=%s, role=%s,
                   password_hash=%s, updated_at=%s, is_active=%s
               WHERE id=%s""",
            (
                employee.username, employee.display_name, employee.email,
                employee.role, employee.password_hash,
                _to_dt(employee.updated_at), int(employee.is_active),
                employee.id,
            ),
        )
        return count > 0

    def delete_account(self, emp_id: str) -> bool:
        count = self._execute(
            "DELETE FROM accounts WHERE id = %s", (emp_id,)
        )
        return count > 0

    def username_exists(self, username: str, exclude_id: str = "") -> bool:
        row = self._execute(
            "SELECT COUNT(*) FROM accounts WHERE LOWER(username)=LOWER(%s) AND id != %s",
            (username, exclude_id), fetch="one",
        )
        return row[0] > 0

    # ------------------------------------------------------------------ #
    # Settings
    # ------------------------------------------------------------------ #

    def load_settings(self) -> dict:
        row = self._execute(
            "SELECT settings_json FROM app_settings WHERE id = 1", fetch="one"
        )
        if row is None:
            return DEFAULT_SETTINGS.copy()
        try:
            loaded = json.loads(row[0])
            merged = DEFAULT_SETTINGS.copy()
            merged.update(loaded)
            return merged
        except (json.JSONDecodeError, TypeError):
            return DEFAULT_SETTINGS.copy()

    def save_settings(self, settings: dict) -> None:
        self._execute(
            """INSERT INTO app_settings (id, settings_json)
               VALUES (1, %s)
               ON DUPLICATE KEY UPDATE
                   settings_json = VALUES(settings_json),
                   updated_at    = NOW()""",
            (json.dumps(settings),),
        )

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
        session_id = "sess_" + uuid.uuid4().hex[:8]
        date_str = datetime.now().strftime("%Y-%m-%d")
        login_time = datetime.now().replace(microsecond=0)
        self._execute(
            """INSERT INTO sessions (session_id, employee_id, date_str, login_time)
               VALUES (%s, %s, %s, %s)""",
            (session_id, employee_id, date_str, login_time),
        )
        return session_id

    def end_session(self, employee_id: str, session_id: str) -> None:
        logout_time = datetime.now().replace(microsecond=0)
        self._execute(
            "UPDATE sessions SET logout_time = %s WHERE session_id = %s",
            (logout_time, session_id),
        )

    # ------------------------------------------------------------------ #
    # Activity buckets
    # ------------------------------------------------------------------ #

    def append_bucket(self, employee_id: str, session_id: str, bucket_dict: dict) -> None:
        minute_bucket = _to_dt(bucket_dict["minute_bucket"])
        self._execute(
            """INSERT INTO activity_buckets
               (session_id, employee_id, minute_bucket, keystrokes, mouse_clicks,
                mouse_scroll_ticks, mouse_distance_px, active_window_title,
                idle_seconds, productivity_score)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                session_id, employee_id, minute_bucket,
                bucket_dict["keystrokes"],
                bucket_dict["mouse_clicks"],
                bucket_dict["mouse_scroll_ticks"],
                round(bucket_dict["mouse_distance_px"], 1),
                bucket_dict.get("active_window_title", "")[:500],
                bucket_dict["idle_seconds"],
                bucket_dict["productivity_score"],
            ),
        )

    def add_screenshot_record(self, employee_id: str, session_id: str, record: dict) -> None:
        captured_at = _to_dt(record["captured_at"])
        ftp_url = record.get("ftp_url") or None
        self._execute(
            """INSERT INTO screenshots (session_id, employee_id, filename, captured_at, ftp_url)
               VALUES (%s, %s, %s, %s, %s)""",
            (session_id, employee_id, record["filename"], captured_at, ftp_url),
        )

    # ------------------------------------------------------------------ #
    # Query helpers
    # ------------------------------------------------------------------ #

    def get_today_summary(self, employee_id: str) -> dict:
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Each bucket covers BUCKET_SECONDS of tracking time (flush interval in tracker.py).
        # idle_seconds is a point-in-time snapshot so we cap it per bucket to avoid
        # accumulation across consecutive idle periods inflating the total.
        BUCKET_SECONDS = 300  # must match _flush_loop timeout in core/tracker.py

        stats = self._execute(
            """SELECT
                   COALESCE(SUM(keystrokes),                    0)   AS keystrokes,
                   COALESCE(SUM(mouse_clicks),                  0)   AS clicks,
                   COALESCE(SUM(mouse_scroll_ticks),            0)   AS scroll_ticks,
                   COALESCE(SUM(mouse_distance_px),            0.0)  AS mouse_distance_px,
                   COALESCE(SUM(LEAST(idle_seconds, %s)),       0)   AS idle_seconds,
                   COALESCE(AVG(productivity_score),           0.0)  AS avg_productivity,
                   COUNT(*)                                          AS bucket_count
               FROM activity_buckets
               WHERE employee_id = %s AND DATE(minute_bucket) = %s""",
            (BUCKET_SECONDS, employee_id, date_str), fetch="one", dictionary=True,
        )

        bucket_count = int(stats["bucket_count"]) if stats else 0
        idle_s = int(stats["idle_seconds"]) if stats else 0
        active_s = max(0, bucket_count * BUCKET_SECONDS - idle_s)

        ss = self._execute(
            "SELECT COUNT(*) FROM screenshots WHERE employee_id=%s AND DATE(captured_at)=%s",
            (employee_id, date_str), fetch="one",
        )
        screenshots_count = int(ss[0]) if ss else 0

        active_row = self._execute(
            """SELECT COUNT(*) FROM sessions
               WHERE employee_id=%s AND date_str=%s AND logout_time IS NULL""",
            (employee_id, date_str), fetch="one",
        )
        is_active = bool(active_row and active_row[0] > 0)

        return {
            "keystrokes":        int(stats["keystrokes"])      if stats else 0,
            "clicks":            int(stats["clicks"])          if stats else 0,
            "scroll_ticks":      int(stats["scroll_ticks"])    if stats else 0,
            "mouse_distance_px": float(stats["mouse_distance_px"]) if stats else 0.0,
            "active_seconds":    active_s,
            "idle_seconds":      idle_s,   # capped at BUCKET_SECONDS per bucket
            "screenshots_count": screenshots_count,
            "avg_productivity":  round(float(stats["avg_productivity"]), 1) if stats and stats["avg_productivity"] else 0.0,
            "is_active_today":   is_active,
        }

    def get_hourly_scores(self, employee_id: str, date_str: str) -> list:
        rows = self._execute(
            """SELECT HOUR(minute_bucket) AS hour,
                      AVG(productivity_score) AS avg_score
               FROM activity_buckets
               WHERE employee_id = %s AND DATE(minute_bucket) = %s
               GROUP BY HOUR(minute_bucket)""",
            (employee_id, date_str), fetch="all", dictionary=True,
        )
        hourly = [0.0] * 24
        for row in rows:
            hourly[int(row["hour"])] = round(float(row["avg_score"]), 1)
        return hourly

    def load_activity(self, employee_id: str, date_str: str) -> dict:
        """
        Return activity data in the same nested-dict structure that report_viewer expects:
        { sessions: [{ session_id, login_time, logout_time, summary, buckets, screenshots }] }
        """
        sess_rows = self._execute(
            """SELECT session_id, login_time, logout_time
               FROM sessions
               WHERE employee_id = %s AND date_str = %s
               ORDER BY login_time""",
            (employee_id, date_str), fetch="all", dictionary=True,
        )

        sessions = []
        for sr in sess_rows:
            sid = sr["session_id"]

            bucket_rows = self._execute(
                """SELECT minute_bucket, keystrokes, mouse_clicks, mouse_scroll_ticks,
                          mouse_distance_px, active_window_title, idle_seconds,
                          productivity_score
                   FROM activity_buckets
                   WHERE session_id = %s
                   ORDER BY minute_bucket""",
                (sid,), fetch="all", dictionary=True,
            )

            buckets = [
                {
                    "minute_bucket":      _to_iso(b["minute_bucket"]),
                    "keystrokes":         b["keystrokes"],
                    "mouse_clicks":       b["mouse_clicks"],
                    "mouse_scroll_ticks": b["mouse_scroll_ticks"],
                    "mouse_distance_px":  b["mouse_distance_px"],
                    "active_window_title": b.get("active_window_title", ""),
                    "idle_seconds":       b["idle_seconds"],
                    "productivity_score": b["productivity_score"],
                }
                for b in bucket_rows
            ]

            ss_count_row = self._execute(
                "SELECT COUNT(*) FROM screenshots WHERE session_id = %s",
                (sid,), fetch="one",
            )
            ss_count = int(ss_count_row[0]) if ss_count_row else 0

            summary = self._compute_summary(buckets, ss_count)

            sessions.append({
                "session_id":  sid,
                "login_time":  _to_iso(sr["login_time"]),
                "logout_time": _to_iso(sr["logout_time"]),
                "buckets":     buckets,
                "screenshots": [],   # paths not needed here; see get_all_screenshots_for_date
                "summary":     summary,
            })

        return {
            "schema_version": 1,
            "employee_id":    employee_id,
            "date":           date_str,
            "sessions":       sessions,
        }

    @staticmethod
    def _compute_summary(buckets: list, screenshots_count: int) -> dict:
        if not buckets:
            return {
                "total_keystrokes": 0, "total_clicks": 0,
                "total_scroll_ticks": 0, "total_mouse_distance_px": 0.0,
                "total_active_seconds": 0, "total_idle_seconds": 0,
                "screenshots_count": screenshots_count,
                "average_productivity_score": 0.0,
            }
        total_idle = sum(b["idle_seconds"] for b in buckets)
        scores = [b["productivity_score"] for b in buckets]
        return {
            "total_keystrokes":          sum(b["keystrokes"]         for b in buckets),
            "total_clicks":              sum(b["mouse_clicks"]        for b in buckets),
            "total_scroll_ticks":        sum(b["mouse_scroll_ticks"]  for b in buckets),
            "total_mouse_distance_px":   sum(b["mouse_distance_px"]   for b in buckets),
            "total_active_seconds":      max(0, len(buckets) * 60 - total_idle),
            "total_idle_seconds":        total_idle,
            "screenshots_count":         screenshots_count,
            "average_productivity_score": round(sum(scores) / len(scores), 1),
        }

    def get_all_screenshots_for_date(self, employee_id: str, date_str: str) -> list:
        """Return list of local Path objects or FTP URL strings for each screenshot."""
        rows = self._execute(
            """SELECT filename, ftp_url FROM screenshots
               WHERE employee_id = %s AND DATE(captured_at) = %s
               ORDER BY captured_at""",
            (employee_id, date_str), fetch="all",
        )
        screenshots_dir = LOGS_DIR / date_str / "screenshots"
        items = []
        for filename, ftp_url in rows:
            p = screenshots_dir / filename
            if p.exists():
                items.append(p)
            elif ftp_url:
                items.append(ftp_url)
        return items

    def get_all_activity_dates(self, employee_id: str) -> list:
        rows = self._execute(
            """SELECT DISTINCT date_str FROM sessions
               WHERE employee_id = %s
               ORDER BY date_str DESC""",
            (employee_id,), fetch="all",
        )
        return [row[0] for row in rows]

"""
AWS Lambda handler for Claude Tracker.
All MySQL logic lives here — DB credentials never leave this function.

Environment variables required:
  DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT (optional, default 3306)

Deploy:
  mkdir lambda_pkg
  pip install mysql-connector-python bcrypt -t lambda_pkg/
  cp lambda_function.py lambda_pkg/
  cd lambda_pkg && zip -r ../tracker_lambda.zip .
  aws lambda update-function-code --function-name tracker --zip-file fileb://tracker_lambda.zip
"""

import json
import os
import uuid
from datetime import datetime
from typing import Optional

import bcrypt
import mysql.connector
from mysql.connector import pooling

# Module-level pool — persists across warm invocations on the same container.
_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="lp",
            pool_size=3,
            host=os.environ["DB_HOST"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"],
            port=int(os.environ.get("DB_PORT", 3306)),
            autocommit=True,
            connection_timeout=10,
            use_pure=True,
        )
    return _pool


def _execute(query, params=None, fetch=None, dictionary=False):
    conn = _get_pool().get_connection()
    try:
        cur = conn.cursor(dictionary=dictionary)
        cur.execute(query, params or ())
        if fetch == "one":
            return cur.fetchone()
        if fetch == "all":
            return cur.fetchall()
        return cur.rowcount
    finally:
        conn.close()


def _to_iso(val) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat(timespec="seconds")
    return str(val)


def _to_dt(val) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(val)


def _ok(body):
    return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}


def _err(msg, code=400):
    return {"statusCode": code, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": msg})}


def _row_to_account(row: dict) -> dict:
    row = dict(row)
    row["created_at"] = _to_iso(row.get("created_at"))
    row["updated_at"] = _to_iso(row.get("updated_at"))
    row["is_active"] = bool(row.get("is_active"))
    return row


# ------------------------------------------------------------------ #
# Route handlers
# ------------------------------------------------------------------ #

def handle_is_first_run(body, path_params, query_params):
    row = _execute("SELECT COUNT(*) FROM accounts", fetch="one")
    return _ok({"is_first_run": row[0] == 0})


def handle_authenticate(body, path_params, query_params):
    username = body.get("username", "")
    password = body.get("password", "")
    row = _execute(
        "SELECT * FROM accounts WHERE LOWER(username)=LOWER(%s)",
        (username,), fetch="one", dictionary=True,
    )
    if not row:
        return _err("Invalid username or password.", 401)
    if not row["is_active"]:
        return _err("This account has been disabled.", 403)
    try:
        ok = bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8"))
    except Exception:
        ok = False
    if not ok:
        return _err("Invalid username or password.", 401)
    return _ok({"account": _row_to_account(row)})


def handle_get_accounts(body, path_params, query_params):
    username = query_params.get("username")
    if username:
        row = _execute(
            "SELECT * FROM accounts WHERE LOWER(username)=LOWER(%s)",
            (username,), fetch="one", dictionary=True,
        )
        return _ok({"account": _row_to_account(row) if row else None})
    rows = _execute("SELECT * FROM accounts ORDER BY display_name", fetch="all", dictionary=True)
    return _ok({"accounts": [_row_to_account(r) for r in rows]})


def handle_get_account(body, path_params, query_params):
    emp_id = path_params.get("id", "")
    row = _execute("SELECT * FROM accounts WHERE id=%s", (emp_id,), fetch="one", dictionary=True)
    return _ok({"account": _row_to_account(row) if row else None})


def handle_create_account(body, path_params, query_params):
    _execute(
        """INSERT INTO accounts
           (id, username, display_name, email, role, password_hash, created_at, updated_at, is_active)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            body["id"], body["username"], body["display_name"],
            body.get("email", ""), body["role"], body["password_hash"],
            _to_dt(body.get("created_at")), _to_dt(body.get("updated_at")),
            int(bool(body.get("is_active", True))),
        ),
    )
    return _ok({"created": True})


def handle_update_account(body, path_params, query_params):
    emp_id = path_params.get("id", "")
    count = _execute(
        """UPDATE accounts
           SET username=%s, display_name=%s, email=%s, role=%s,
               password_hash=%s, updated_at=%s, is_active=%s
           WHERE id=%s""",
        (
            body["username"], body["display_name"], body.get("email", ""),
            body["role"], body["password_hash"],
            _to_dt(body.get("updated_at")), int(bool(body.get("is_active", True))),
            emp_id,
        ),
    )
    return _ok({"updated": count > 0})


def handle_delete_account(body, path_params, query_params):
    emp_id = path_params.get("id", "")
    count = _execute("DELETE FROM accounts WHERE id=%s", (emp_id,))
    return _ok({"deleted": count > 0})


def handle_check_username(body, path_params, query_params):
    username = query_params.get("username", "")
    exclude_id = query_params.get("exclude_id", "")
    row = _execute(
        "SELECT COUNT(*) FROM accounts WHERE LOWER(username)=LOWER(%s) AND id != %s",
        (username, exclude_id), fetch="one",
    )
    return _ok({"exists": row[0] > 0})


def handle_load_settings(body, path_params, query_params):
    row = _execute("SELECT settings_json FROM app_settings WHERE id=1", fetch="one")
    if row is None:
        return _ok({"settings": {}})
    try:
        return _ok({"settings": json.loads(row[0])})
    except Exception:
        return _ok({"settings": {}})


def handle_save_settings(body, path_params, query_params):
    settings = body.get("settings", {})
    _execute(
        """INSERT INTO app_settings (id, settings_json)
           VALUES (1, %s)
           ON DUPLICATE KEY UPDATE settings_json=VALUES(settings_json), updated_at=NOW()""",
        (json.dumps(settings),),
    )
    return _ok({"saved": True})


def handle_start_session(body, path_params, query_params):
    employee_id = body["employee_id"]
    session_id = "sess_" + uuid.uuid4().hex[:8]
    date_str = datetime.now().strftime("%Y-%m-%d")
    login_time = datetime.now().replace(microsecond=0)
    _execute(
        "INSERT INTO sessions (session_id, employee_id, date_str, login_time) VALUES (%s, %s, %s, %s)",
        (session_id, employee_id, date_str, login_time),
    )
    return _ok({"session_id": session_id})


def handle_end_session(body, path_params, query_params):
    logout_time = datetime.now().replace(microsecond=0)
    _execute(
        "UPDATE sessions SET logout_time=%s WHERE session_id=%s",
        (logout_time, body["session_id"]),
    )
    return _ok({"ended": True})


def handle_append_bucket(body, path_params, query_params):
    bucket = body["bucket"]
    _execute(
        """INSERT INTO activity_buckets
           (session_id, employee_id, minute_bucket, keystrokes, mouse_clicks,
            mouse_scroll_ticks, mouse_distance_px, active_window_title, idle_seconds, productivity_score)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            body["session_id"], body["employee_id"],
            _to_dt(bucket["minute_bucket"]),
            bucket["keystrokes"],
            bucket["mouse_clicks"],
            bucket["mouse_scroll_ticks"],
            round(float(bucket["mouse_distance_px"]), 1),
            bucket.get("active_window_title", "")[:500],
            bucket["idle_seconds"],
            bucket["productivity_score"],
        ),
    )
    return _ok({"appended": True})


def handle_add_screenshot(body, path_params, query_params):
    record = body["record"]
    _execute(
        "INSERT INTO screenshots (session_id, employee_id, filename, captured_at, ftp_url) VALUES (%s, %s, %s, %s, %s)",
        (
            body["session_id"], body["employee_id"],
            record["filename"],
            _to_dt(record["captured_at"]),
            record.get("ftp_url") or None,
        ),
    )
    return _ok({"recorded": True})


def handle_get_today_summary(body, path_params, query_params):
    employee_id = query_params.get("employee_id", "")
    date_str = datetime.now().strftime("%Y-%m-%d")
    BUCKET_SECONDS = 300

    stats = _execute(
        """SELECT
               COALESCE(SUM(keystrokes), 0)                           AS keystrokes,
               COALESCE(SUM(mouse_clicks), 0)                         AS clicks,
               COALESCE(SUM(mouse_scroll_ticks), 0)                   AS scroll_ticks,
               COALESCE(SUM(mouse_distance_px), 0.0)                  AS mouse_distance_px,
               COALESCE(SUM(LEAST(idle_seconds, %s)), 0)              AS idle_seconds,
               COALESCE(AVG(productivity_score), 0.0)                 AS avg_productivity,
               COUNT(*)                                                AS bucket_count
           FROM activity_buckets
           WHERE employee_id=%s AND DATE(minute_bucket)=%s""",
        (BUCKET_SECONDS, employee_id, date_str), fetch="one", dictionary=True,
    )

    idle_s = int(stats["idle_seconds"]) if stats else 0

    session_time_row = _execute(
        """SELECT COALESCE(SUM(TIMESTAMPDIFF(SECOND, login_time,
               COALESCE(logout_time, NOW()))), 0) AS total_seconds
           FROM sessions WHERE employee_id=%s AND date_str=%s""",
        (employee_id, date_str), fetch="one", dictionary=True,
    )
    total_session_seconds = int(session_time_row["total_seconds"]) if session_time_row else 0
    active_s = max(0, total_session_seconds - idle_s)

    completed_row = _execute(
        """SELECT COALESCE(SUM(TIMESTAMPDIFF(SECOND, login_time, logout_time)), 0) AS total
           FROM sessions WHERE employee_id=%s AND date_str=%s AND logout_time IS NOT NULL""",
        (employee_id, date_str), fetch="one", dictionary=True,
    )
    completed_s = int(completed_row["total"]) if completed_row else 0

    ss = _execute(
        "SELECT COUNT(*) FROM screenshots WHERE employee_id=%s AND DATE(captured_at)=%s",
        (employee_id, date_str), fetch="one",
    )
    screenshots_count = int(ss[0]) if ss else 0

    active_row = _execute(
        "SELECT COUNT(*) FROM sessions WHERE employee_id=%s AND date_str=%s AND logout_time IS NULL",
        (employee_id, date_str), fetch="one",
    )
    is_active = bool(active_row and active_row[0] > 0)

    return _ok({
        "keystrokes":        int(stats["keystrokes"])           if stats else 0,
        "clicks":            int(stats["clicks"])               if stats else 0,
        "scroll_ticks":      int(stats["scroll_ticks"])         if stats else 0,
        "mouse_distance_px": float(stats["mouse_distance_px"])  if stats else 0.0,
        "active_seconds":    active_s,
        "idle_seconds":      idle_s,
        "completed_seconds": completed_s,
        "screenshots_count": screenshots_count,
        "avg_productivity":  round(float(stats["avg_productivity"]), 1) if stats and stats["avg_productivity"] else 0.0,
        "is_active_today":   is_active,
    })


def handle_get_hourly(body, path_params, query_params):
    employee_id = query_params.get("employee_id", "")
    date_str = query_params.get("date_str", "")
    rows = _execute(
        """SELECT HOUR(minute_bucket) AS hour, AVG(productivity_score) AS avg_score
           FROM activity_buckets
           WHERE employee_id=%s AND DATE(minute_bucket)=%s
           GROUP BY HOUR(minute_bucket)""",
        (employee_id, date_str), fetch="all", dictionary=True,
    )
    hourly = [0.0] * 24
    for row in rows:
        hourly[int(row["hour"])] = round(float(row["avg_score"]), 1)
    return _ok({"hourly": hourly})


def handle_load_activity(body, path_params, query_params):
    employee_id = query_params.get("employee_id", "")
    date_str = query_params.get("date_str", "")

    sess_rows = _execute(
        "SELECT session_id, login_time, logout_time FROM sessions WHERE employee_id=%s AND date_str=%s ORDER BY login_time",
        (employee_id, date_str), fetch="all", dictionary=True,
    )

    sessions = []
    for sr in sess_rows:
        sid = sr["session_id"]
        bucket_rows = _execute(
            """SELECT minute_bucket, keystrokes, mouse_clicks, mouse_scroll_ticks,
                      mouse_distance_px, active_window_title, idle_seconds, productivity_score
               FROM activity_buckets WHERE session_id=%s ORDER BY minute_bucket""",
            (sid,), fetch="all", dictionary=True,
        )
        buckets = [
            {
                "minute_bucket":       _to_iso(b["minute_bucket"]),
                "keystrokes":          b["keystrokes"],
                "mouse_clicks":        b["mouse_clicks"],
                "mouse_scroll_ticks":  b["mouse_scroll_ticks"],
                "mouse_distance_px":   float(b["mouse_distance_px"]),
                "active_window_title": b.get("active_window_title", ""),
                "idle_seconds":        b["idle_seconds"],
                "productivity_score":  float(b["productivity_score"]),
            }
            for b in bucket_rows
        ]

        ss_count_row = _execute("SELECT COUNT(*) FROM screenshots WHERE session_id=%s", (sid,), fetch="one")
        ss_count = int(ss_count_row[0]) if ss_count_row else 0

        login_dt = _to_dt(sr["login_time"])
        logout_dt = _to_dt(sr["logout_time"]) if sr["logout_time"] else datetime.now().replace(microsecond=0)
        session_duration = max(0, int((logout_dt - login_dt).total_seconds()))

        BUCKET_SECONDS = 300
        total_idle = sum(min(b["idle_seconds"], BUCKET_SECONDS) for b in buckets)
        active_seconds = max(0, session_duration - total_idle)
        scores = [b["productivity_score"] for b in buckets]
        summary = {
            "total_keystrokes":           sum(b["keystrokes"]        for b in buckets),
            "total_clicks":               sum(b["mouse_clicks"]       for b in buckets),
            "total_scroll_ticks":         sum(b["mouse_scroll_ticks"] for b in buckets),
            "total_mouse_distance_px":    sum(b["mouse_distance_px"]  for b in buckets),
            "total_active_seconds":       active_seconds,
            "total_idle_seconds":         total_idle,
            "screenshots_count":          ss_count,
            "average_productivity_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        }

        sessions.append({
            "session_id":  sid,
            "login_time":  _to_iso(sr["login_time"]),
            "logout_time": _to_iso(sr["logout_time"]),
            "buckets":     buckets,
            "screenshots": [],
            "summary":     summary,
        })

    return _ok({"schema_version": 1, "employee_id": employee_id, "date": date_str, "sessions": sessions})


def handle_get_screenshots(body, path_params, query_params):
    employee_id = query_params.get("employee_id", "")
    date_str = query_params.get("date_str", "")
    rows = _execute(
        "SELECT filename, ftp_url FROM screenshots WHERE employee_id=%s AND DATE(captured_at)=%s ORDER BY captured_at",
        (employee_id, date_str), fetch="all",
    )
    screenshots = [{"filename": r[0], "ftp_url": r[1]} for r in rows]
    return _ok({"screenshots": screenshots})


def handle_get_activity_dates(body, path_params, query_params):
    employee_id = query_params.get("employee_id", "")
    rows = _execute(
        "SELECT DISTINCT date_str FROM sessions WHERE employee_id=%s ORDER BY date_str DESC",
        (employee_id,), fetch="all",
    )
    return _ok({"dates": [r[0] for r in rows]})


# ------------------------------------------------------------------ #
# Routing table
# ------------------------------------------------------------------ #

ROUTES = {
    ("GET",    "/tracker/is_first_run"):              handle_is_first_run,
    ("POST",   "/tracker/authenticate"):              handle_authenticate,
    ("GET",    "/tracker/accounts"):                  handle_get_accounts,
    ("GET",    "/tracker/accounts/{id}"):             handle_get_account,
    ("POST",   "/tracker/accounts"):                  handle_create_account,
    ("PUT",    "/tracker/accounts/{id}"):             handle_update_account,
    ("DELETE", "/tracker/accounts/{id}"):             handle_delete_account,
    ("GET",    "/tracker/accounts/check-username"):   handle_check_username,
    ("GET",    "/tracker/settings"):                  handle_load_settings,
    ("POST",   "/tracker/settings"):                  handle_save_settings,
    ("POST",   "/tracker/sessions/start"):            handle_start_session,
    ("POST",   "/tracker/sessions/end"):              handle_end_session,
    ("POST",   "/tracker/buckets"):                   handle_append_bucket,
    ("POST",   "/tracker/screenshots"):               handle_add_screenshot,
    ("GET",    "/tracker/activity/today"):            handle_get_today_summary,
    ("GET",    "/tracker/activity/hourly"):           handle_get_hourly,
    ("GET",    "/tracker/activity"):                  handle_load_activity,
    ("GET",    "/tracker/activity/screenshots"):      handle_get_screenshots,
    ("GET",    "/tracker/activity/dates"):            handle_get_activity_dates,
}


def _match_route(method: str, path: str):
    """Match path against route table, extracting path parameters."""
    for (route_method, route_path), handler in ROUTES.items():
        if route_method != method:
            continue
        route_parts = route_path.split("/")
        path_parts = path.split("/")
        if len(route_parts) != len(path_parts):
            continue
        params = {}
        matched = True
        for rp, pp in zip(route_parts, path_parts):
            if rp.startswith("{") and rp.endswith("}"):
                params[rp[1:-1]] = pp
            elif rp != pp:
                matched = False
                break
        if matched:
            return handler, params
    return None, {}


def lambda_handler(event, context):
    method = event.get("httpMethod", "GET")
    raw_path = event.get("path", "/")
    # API Gateway forwards the full resource path including the mount prefix (/track);
    # strip it so internal routing matches the ROUTES table entries (/tracker/...).
    path = raw_path.removeprefix("/track") or "/"
    try:
        body = json.loads(event.get("body") or "{}")
    except Exception:
        body = {}
    query_params = event.get("queryStringParameters") or {}

    handler, path_params = _match_route(method, path)
    if handler is None:
        return _err(f"Route not found: {method} {path}", 404)

    try:
        return handler(body, path_params, query_params)
    except Exception as e:
        return _err(f"Internal error: {e}", 500)

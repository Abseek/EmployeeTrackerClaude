import ftplib
import io
import random
import sys
import threading
from datetime import datetime

import mss
from PIL import Image

from config import FTP_HOST, FTP_USER, FTP_PASSWORD, FTP_BASE_DIR, FTP_HTTP_BASE


def _ftp_mkdirs(ftp: ftplib.FTP, remote_dir: str):
    """Navigate to remote_dir, creating each missing directory level along the way.
    FTP's MKD only creates one level at a time, so we walk the path component by
    component — same as 'mkdir -p' on the server side."""
    try:
        ftp.cwd(remote_dir)
        return  # already exists, fast path
    except ftplib.error_perm:
        pass

    parts = [p for p in remote_dir.split("/") if p]
    path = ""
    for part in parts:
        path += "/" + part
        try:
            ftp.mkd(path)
        except ftplib.error_perm:
            pass  # already exists at this level
    ftp.cwd(remote_dir)


class ScreenshotEngine:
    def __init__(self, employee_id: str, settings: dict, storage):
        self._employee_id = employee_id
        self._storage = storage
        self._session_id: str = None
        self._min_seconds = settings.get("screenshot_interval_min_seconds", 60)
        self._max_seconds = settings.get("screenshot_interval_max_seconds", 120)
        self._quality = settings.get("screenshot_quality", 85)
        self._max_width = settings.get("screenshot_max_width", 1920)
        self._stop_event = threading.Event()
        self._thread = None
        self._initial_timer = None

    def set_session_id(self, session_id: str):
        self._session_id = session_id

    def update_settings(self, settings: dict):
        self._min_seconds = settings.get("screenshot_interval_min_seconds", self._min_seconds)
        self._max_seconds = settings.get("screenshot_interval_max_seconds", self._max_seconds)
        self._quality = settings.get("screenshot_quality", self._quality)
        self._max_width = settings.get("screenshot_max_width", self._max_width)

    def start(self):
        self._stop_event.clear()

        # Take one screenshot immediately (after 4 s so the screen settles)
        self._initial_timer = threading.Timer(4.0, self._capture_and_save)
        self._initial_timer.daemon = True
        self._initial_timer.start()

        # Then follow the random-interval loop
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._initial_timer is not None:
            self._initial_timer.cancel()
            self._initial_timer = None

    def _loop(self):
        while not self._stop_event.is_set():
            interval = random.randint(
                max(30, self._min_seconds),
                max(60, self._max_seconds),
            )
            self._stop_event.wait(timeout=interval)
            if not self._stop_event.is_set():
                self._capture_and_save()

    def _capture_and_save(self):
        if self._stop_event.is_set():
            return
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            screenshots_dir = self._storage.get_screenshots_dir(date_str)
            timestamp = datetime.now()
            filename = f"{self._employee_id}_{timestamp.strftime('%H-%M-%S')}.jpg"
            path = screenshots_dir / filename

            with mss.mss() as sct:
                monitor = sct.monitors[0]  # all monitors combined
                screenshot = sct.grab(monitor)
                # Use .rgb (correct channel order) instead of .bgra interpreted as RGBA,
                # which swaps the Red and Blue channels in the saved image.
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

            if img.width > self._max_width:
                ratio = self._max_width / img.width
                img = img.resize(
                    (self._max_width, int(img.height * ratio)), Image.LANCZOS
                )

            img.save(str(path), "JPEG", quality=self._quality, optimize=True)

            if self._session_id:
                session_id = self._session_id
                employee_id = self._employee_id
                captured_at = timestamp.isoformat(timespec="seconds")
                # Upload to FTP in background so capture thread isn't blocked
                t = threading.Thread(
                    target=self._upload_and_record,
                    args=(path, date_str, filename, employee_id, session_id, captured_at),
                    daemon=True,
                )
                t.start()
        except Exception as e:
            print(f"[ScreenshotEngine] capture failed: {e}", file=sys.stderr)

    def _upload_and_record(self, local_path, date_str: str, filename: str,
                           employee_id: str, session_id: str, captured_at: str):
        """Upload to FTP then write DB record. Runs in a background thread."""
        ftp_url = ""
        remote_dir = f"{FTP_BASE_DIR}/{date_str}"
        try:
            with ftplib.FTP(FTP_HOST, timeout=30) as ftp:
                ftp.login(FTP_USER, FTP_PASSWORD)
                ftp.set_pasv(True)  # passive mode works through NAT/firewalls
                _ftp_mkdirs(ftp, remote_dir)
                with open(local_path, "rb") as f:
                    ftp.storbinary(f"STOR {filename}", f)
            ftp_url = f"{FTP_HTTP_BASE}/{date_str}/{filename}"
        except Exception as e:
            print(f"[ScreenshotEngine] FTP upload failed: {e}", file=sys.stderr)

        try:
            self._storage.add_screenshot_record(
                employee_id, session_id,
                {"filename": filename, "captured_at": captured_at, "ftp_url": ftp_url},
            )
        except Exception as e:
            print(f"[ScreenshotEngine] DB record failed: {e}", file=sys.stderr)

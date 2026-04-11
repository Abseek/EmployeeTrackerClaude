import threading
from datetime import datetime

try:
    import win32gui
    _WIN32_AVAILABLE = True
except ImportError:
    _WIN32_AVAILABLE = False

from core.activity_analyzer import AtomicCounter, MouseStats, compute_productivity_score
from core.idle_detector import IdleDetector
from core.keyboard_monitor import KeyboardMonitor
from core.mouse_monitor import MouseMonitor
from core.screenshot_engine import ScreenshotEngine
from data.models import ActivityBucket


class Tracker:
    """
    Master tracking orchestrator.
    get_live_stats() returns ONLY the current unflushed bucket accumulators.
    Completed buckets live in storage and are read via get_today_summary().
    Dashboard must NOT add both together — only one source per metric.
    """

    def __init__(self, employee_id: str, settings: dict, storage):
        self._employee_id = employee_id
        self._settings = settings
        self._storage = storage

        self._kb_counter = AtomicCounter()
        self._mouse_stats = MouseStats()
        self._idle_detector = IdleDetector()

        self._kb_monitor = KeyboardMonitor(self._kb_counter)
        self._mouse_monitor = MouseMonitor(self._mouse_stats)
        self._screenshot_engine = ScreenshotEngine(employee_id, settings, storage)

        self._stop_event = threading.Event()
        self._flush_thread = None
        self._session_id: str = None

    @property
    def is_running(self) -> bool:
        return self._session_id is not None

    def start(self):
        if self.is_running:
            return
        self._session_id = self._storage.start_session(self._employee_id)
        self._screenshot_engine.set_session_id(self._session_id)

        self._kb_monitor.start()
        self._mouse_monitor.start()
        self._screenshot_engine.start()

        self._stop_event.clear()
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

    def stop(self):
        self._stop_event.set()
        self._kb_monitor.stop()
        self._mouse_monitor.stop()
        self._screenshot_engine.stop()
        self._flush_bucket()  # flush remaining partial bucket

        if self._session_id:
            self._storage.end_session(self._employee_id, self._session_id)
            self._session_id = None

    def get_live_stats(self) -> dict:
        """
        Returns ONLY what is accumulating in the current (not-yet-flushed) bucket.
        Do NOT add this to get_today_summary() totals — they cover different data.
        """
        clicks, scroll_ticks, distance_px = self._mouse_stats.snapshot
        return {
            "keystrokes": self._kb_counter.value,
            "clicks": int(clicks),
            "scroll_ticks": int(scroll_ticks),
            "distance_px": distance_px,
            "idle_seconds": self._idle_detector.get_idle_seconds(),
        }

    @property
    def session_id(self) -> str:
        return self._session_id

    def _flush_loop(self):
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=300.0)  # flush every 5 minutes
            if not self._stop_event.is_set():
                self._flush_bucket()

    def _flush_bucket(self):
        bucket_time = datetime.now().replace(second=0, microsecond=0)

        keystrokes = self._kb_counter.get_and_reset()
        clicks, scroll_ticks, distance_px = self._mouse_stats.get_and_reset()
        idle_seconds = self._idle_detector.get_idle_seconds()
        window_title = _get_active_window_title()

        weights = self._settings.get("productivity_weights", {})
        idle_threshold = self._settings.get("idle_threshold_seconds", 300)
        score = compute_productivity_score(
            keystrokes, clicks, scroll_ticks, distance_px, idle_seconds, weights, idle_threshold
        )

        bucket = ActivityBucket(
            minute_bucket=bucket_time.isoformat(timespec="seconds"),
            keystrokes=keystrokes,
            mouse_clicks=clicks,
            mouse_scroll_ticks=scroll_ticks,
            mouse_distance_px=distance_px,
            active_window_title=window_title,
            idle_seconds=idle_seconds,
            productivity_score=score,
        )

        if self._session_id:
            self._storage.append_bucket(
                self._employee_id, self._session_id, bucket.to_dict()
            )


def _get_active_window_title() -> str:
    if not _WIN32_AVAILABLE:
        return ""
    try:
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd) or ""
    except Exception:
        return ""

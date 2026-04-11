import threading

from config import DEFAULT_SETTINGS

# Baselines represent the expected activity for a FULL score on each component
# in a 5-minute bucket window. Anything at or above baseline = 1.0 (full marks).
# These are intentionally modest so normal, focused work scores well.
#   Keystrokes: ~20/min (light typing, reading with occasional input)
#   Clicks:      3/min  (navigating between docs, clicking links)
#   Scroll:      4/min  (scrolling through content)
#   Distance:  300px/min (minimal mouse movement between tasks)
BASELINE_KEYSTROKES = 100
BASELINE_CLICKS = 15
BASELINE_SCROLL_TICKS = 20
BASELINE_DISTANCE_PX = 1500


def _normalize(value: float, baseline: float) -> float:
    """Linear normalization capped at 1.0.
    At or above baseline → 1.0 (full score for that component).
    Below baseline → proportional score.
    This ensures normal work scores well, not just hyperactive work.
    """
    if baseline <= 0:
        return 0.0
    return min(1.0, value / baseline)


def compute_productivity_score(
    keystrokes: int,
    mouse_clicks: int,
    mouse_scroll_ticks: int,
    mouse_distance_px: float,
    idle_seconds: int,
    weights: dict = None,
    idle_threshold: int = None,
) -> float:
    """
    Returns a productivity score 0.0–100.0 for a 5-minute bucket window.
    Higher is more active. idle_threshold is the seconds of inactivity before
    the score starts dropping (defaults to idle_threshold_seconds in settings).
    """
    if weights is None:
        weights = DEFAULT_SETTINGS["productivity_weights"]
    if idle_threshold is None:
        idle_threshold = DEFAULT_SETTINGS["idle_threshold_seconds"]

    k = _normalize(keystrokes, BASELINE_KEYSTROKES)
    c = _normalize(mouse_clicks, BASELINE_CLICKS)
    s = _normalize(mouse_scroll_ticks, BASELINE_SCROLL_TICKS)
    m = _normalize(mouse_distance_px, BASELINE_DISTANCE_PX)

    idle_factor = max(0.0, (idle_threshold - idle_seconds) / idle_threshold)

    raw = (
        k * weights.get("keyboard", 0.40)
        + c * weights.get("mouse_clicks", 0.30)
        + m * weights.get("mouse_movement", 0.20)
        + s * weights.get("mouse_scroll", 0.10)
    )

    score = raw * idle_factor * 100.0
    return round(min(score, 100.0), 1)


class AtomicCounter:
    """Thread-safe integer counter with atomic get-and-reset."""

    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:
            self._value += 1

    def get_and_reset(self) -> int:
        with self._lock:
            val = self._value
            self._value = 0
            return val

    @property
    def value(self) -> int:
        with self._lock:
            return self._value


class MouseStats:
    """Thread-safe accumulator for mouse metrics."""

    def __init__(self):
        self._clicks = 0
        self._scroll_ticks = 0
        self._distance_px = 0.0
        self._last_x: int = None
        self._last_y: int = None
        self._lock = threading.Lock()

    def add_click(self):
        with self._lock:
            self._clicks += 1

    def add_scroll(self, ticks: int = 1):
        with self._lock:
            self._scroll_ticks += abs(ticks)

    def update_position(self, x: int, y: int):
        with self._lock:
            if self._last_x is not None and self._last_y is not None:
                dx = x - self._last_x
                dy = y - self._last_y
                self._distance_px += (dx * dx + dy * dy) ** 0.5
            self._last_x = x
            self._last_y = y

    def get_and_reset(self) -> tuple:
        """Returns (clicks, scroll_ticks, distance_px) and resets all."""
        with self._lock:
            clicks = self._clicks
            scroll = self._scroll_ticks
            dist = self._distance_px
            self._clicks = 0
            self._scroll_ticks = 0
            self._distance_px = 0.0
            self._last_x = None
            self._last_y = None
            return clicks, scroll, dist

    @property
    def snapshot(self) -> tuple:
        """Non-resetting read for live display."""
        with self._lock:
            return self._clicks, self._scroll_ticks, self._distance_px

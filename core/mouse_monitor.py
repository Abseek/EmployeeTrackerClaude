import time

from pynput import mouse

from core.activity_analyzer import MouseStats

_MOVE_INTERVAL = 0.05  # process at most 20 move events per second


class MouseMonitor:
    def __init__(self, stats: MouseStats):
        self._stats = stats
        self._listener = None
        self._last_move_time = 0.0

    def start(self):
        self._listener = mouse.Listener(
            on_click=self._on_click,
            on_scroll=self._on_scroll,
            on_move=self._on_move,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _on_click(self, x, y, button, pressed):
        if pressed:
            self._stats.add_click()

    def _on_scroll(self, x, y, dx, dy):
        self._stats.add_scroll(int(abs(dy)) or 1)

    def _on_move(self, x, y):
        # Throttle: process at most 20 positions/second instead of every pixel.
        # Reduces hook-thread CPU load and lock contention during long shifts.
        now = time.monotonic()
        if now - self._last_move_time >= _MOVE_INTERVAL:
            self._stats.update_position(x, y)
            self._last_move_time = now

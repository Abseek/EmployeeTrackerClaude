from pynput import keyboard

from core.activity_analyzer import AtomicCounter


class KeyboardMonitor:
    def __init__(self, counter: AtomicCounter):
        self._counter = counter
        self._listener = None

    def start(self):
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            suppress=False,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key):
        self._counter.increment()

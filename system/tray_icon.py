import threading

try:
    import pystray
    from PIL import Image
    _PYSTRAY_AVAILABLE = True
except ImportError:
    _PYSTRAY_AVAILABLE = False

from config import ICON_PNG, APP_NAME


class TrayIcon:
    def __init__(self, app_ref):
        self._app = app_ref
        self._icon = None
        self._thread = None

    def start(self):
        if not _PYSTRAY_AVAILABLE:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None

    def _run(self):
        try:
            img = self._load_icon()
            menu = pystray.Menu(
                pystray.MenuItem("Show Window", self._on_show, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._on_quit),
            )
            self._icon = pystray.Icon(APP_NAME, img, APP_NAME, menu)
            self._icon.run()
        except Exception:
            pass

    def _load_icon(self):
        if ICON_PNG.exists():
            img = Image.open(str(ICON_PNG))
            return img.resize((64, 64))
        # Fallback: solid blue square
        return Image.new("RGB", (64, 64), color="#2D7DD2")

    def _on_show(self, icon, item):
        if self._app:
            self._app.after(0, self._restore_window)

    def _restore_window(self):
        self.stop()
        self._app.deiconify()
        self._app.lift()
        self._app.focus_force()

    def _on_quit(self, icon, item):
        if self._app:
            self._app.after(0, self._app.quit_app)

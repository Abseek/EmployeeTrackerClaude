import sys

try:
    import win32event
    import win32api
    import winerror
    _WIN32_AVAILABLE = True
except ImportError:
    _WIN32_AVAILABLE = False

_MUTEX_HANDLE = None
MUTEX_NAME = "EmployeeTracker_SingleInstance_Mutex"


def enforce_single_instance():
    """
    Create a named Win32 mutex. If another instance already holds it,
    show a message and exit.

    The returned handle must be kept alive for the process lifetime —
    store it in the module-level _MUTEX_HANDLE so GC does not release it.
    """
    global _MUTEX_HANDLE

    if not _WIN32_AVAILABLE:
        return  # Non-Windows fallback: skip enforcement

    _MUTEX_HANDLE = win32event.CreateMutex(None, False, MUTEX_NAME)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            from config import WINDOW_TITLE
            hwnd = user32.FindWindowW(None, WINDOW_TITLE)
            if hwnd:
                SW_RESTORE = 9
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
            else:
                user32.MessageBoxW(
                    0,
                    "Employee Tracker is already running.\n\nCheck the system tray.",
                    "Already Running",
                    0x30,
                )
        except Exception:
            pass
        sys.exit(0)

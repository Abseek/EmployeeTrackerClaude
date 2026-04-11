import os
import sys
from pathlib import Path

# Database connection
DB_HOST = "193.203.184.197"
DB_USER = "u420709713_Abhishek"
DB_PASSWORD = "Abhishek#77699"
DB_NAME = "u420709713_Claude_Tracker"
DB_PORT = 3306

# FTP for screenshot hosting
FTP_HOST = "ftp.shophoustondiamonddistrict.com"
FTP_USER = "u420709713.ClaudeTracker"
FTP_PASSWORD = "Abhishek#77699"
FTP_BASE_DIR = "/home/u420709713/domains/shophoustondiamonddistrict.com/claudeTracker"
FTP_HTTP_BASE = "https://shophoustondiamonddistrict.com/claudeTracker"

APP_NAME = "EmployeeTracker"
APP_VERSION = "1.0.0"
WINDOW_TITLE = "Employee Tracker"
WINDOW_SIZE = "1200x800"
WINDOW_MIN = (900, 600)

# Runtime data directory
DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
LOGS_DIR = DATA_DIR / "logs"

# UI Colors
COLOR_ACCENT = "#2D7DD2"
COLOR_ACCENT_HOVER = "#1a5fa8"
COLOR_SUCCESS = "#27ae60"
COLOR_WARNING = "#f39c12"
COLOR_DANGER = "#e74c3c"
COLOR_BG = "#1a1a2e"
COLOR_CARD = "#16213e"
COLOR_SIDEBAR = "#0f3460"
COLOR_SIDEBAR_BTN = "#1a4a7a"
COLOR_SIDEBAR_ACTIVE = "#2D7DD2"
COLOR_TEXT = "#e0e0e0"
COLOR_TEXT_MUTED = "#8899aa"
COLOR_BORDER = "#2a3a5a"

# Productivity score bands
SCORE_BANDS = [
    (81, 100, COLOR_SUCCESS, "Highly Active"),
    (61, 80, COLOR_ACCENT, "Active"),
    (31, 60, COLOR_WARNING, "Moderate"),
    (0, 30, COLOR_DANGER, "Low Activity"),
]

# Default settings
DEFAULT_SETTINGS = {
    "schema_version": 1,
    # Screenshots taken at a random interval between min and max (seconds).
    # 3–8 min range is fair: frequent enough to verify work, not so frequent
    # it catches every natural pause (reading, thinking, calls).
    "screenshot_interval_min_seconds": 180,
    "screenshot_interval_max_seconds": 480,
    # Seconds of no keyboard/mouse input before a period is counted as idle.
    # 300s (5 min) matches the bucket flush window and is fair — covers reading
    # documents, attending calls, or thinking without penalising the employee.
    "idle_threshold_seconds": 300,
    "screenshot_quality": 60,
    "screenshot_max_width": 1280,
    "productivity_weights": {
        "keyboard": 0.40,
        "mouse_clicks": 0.30,
        "mouse_movement": 0.20,
        "mouse_scroll": 0.10,
    },
    "autostart_enabled": False,
    "minimize_to_tray": True,
}


def resource_path(relative_path: str) -> Path:
    """Resolve asset path for both source and frozen .exe."""
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return base / relative_path


ICON_ICO = resource_path("assets/icon.ico")
ICON_PNG = resource_path("assets/icon.png")


def score_color(score: float) -> str:
    """Return color hex for a productivity score."""
    for low, high, color, _ in SCORE_BANDS:
        if low <= score <= high:
            return color
    return COLOR_TEXT_MUTED


def score_label(score: float) -> str:
    """Return text label for a productivity score."""
    for low, high, _, label in SCORE_BANDS:
        if low <= score <= high:
            return label
    return "No Data"

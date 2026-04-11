"""
Employee Tracker — Entry Point
"""
from config import DATA_DIR, LOGS_DIR
from system.single_instance import enforce_single_instance


def main():
    # Enforce single instance (Win32 named mutex)
    enforce_single_instance()

    # Ensure data directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Launch app
    from app import EmployeeTrackerApp
    app = EmployeeTrackerApp()
    app.mainloop()


if __name__ == "__main__":
    main()

"""
create_tables.py  —  Run once to set up the MySQL database schema.

Usage:
    pip install mysql-connector-python
    python create_tables.py
"""

import sys
import mysql.connector
from mysql.connector import Error as MySQLError

DB_CONFIG = {
    "host":     "193.203.184.197",
    "user":     "u420709713_Abhishek",
    "password": "Abhishek#77699",
    "database": "u420709713_Claude_Tracker",
    "port":     3306,
    "connection_timeout": 15,
}

TABLES = {
    "accounts": """
        CREATE TABLE IF NOT EXISTS accounts (
            id           VARCHAR(20)  NOT NULL,
            username     VARCHAR(100) NOT NULL,
            display_name VARCHAR(200) NOT NULL,
            email        VARCHAR(200) DEFAULT '',
            role         ENUM('admin','employee') NOT NULL DEFAULT 'employee',
            password_hash VARCHAR(200) NOT NULL,
            created_at   DATETIME     NOT NULL,
            updated_at   DATETIME     NOT NULL,
            is_active    TINYINT(1)   NOT NULL DEFAULT 1,
            PRIMARY KEY (id),
            UNIQUE KEY uq_username (username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,

    "app_settings": """
        CREATE TABLE IF NOT EXISTS app_settings (
            id            INT  NOT NULL DEFAULT 1,
            settings_json TEXT NOT NULL,
            updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                          ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,

    "sessions": """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id  VARCHAR(20) NOT NULL,
            employee_id VARCHAR(20) NOT NULL,
            date_str    VARCHAR(10) NOT NULL,
            login_time  DATETIME    NOT NULL,
            logout_time DATETIME    DEFAULT NULL,
            PRIMARY KEY (session_id),
            INDEX idx_employee_date (employee_id, date_str)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,

    "activity_buckets": """
        CREATE TABLE IF NOT EXISTS activity_buckets (
            id                  BIGINT  NOT NULL AUTO_INCREMENT,
            session_id          VARCHAR(20)  NOT NULL,
            employee_id         VARCHAR(20)  NOT NULL,
            minute_bucket       DATETIME     NOT NULL,
            keystrokes          INT          NOT NULL DEFAULT 0,
            mouse_clicks        INT          NOT NULL DEFAULT 0,
            mouse_scroll_ticks  INT          NOT NULL DEFAULT 0,
            mouse_distance_px   FLOAT        NOT NULL DEFAULT 0.0,
            active_window_title VARCHAR(500) DEFAULT '',
            idle_seconds        INT          NOT NULL DEFAULT 0,
            productivity_score  FLOAT        NOT NULL DEFAULT 0.0,
            PRIMARY KEY (id),
            INDEX idx_employee_bucket (employee_id, minute_bucket),
            INDEX idx_session_id      (session_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,

    "screenshots": """
        CREATE TABLE IF NOT EXISTS screenshots (
            id          BIGINT      NOT NULL AUTO_INCREMENT,
            session_id  VARCHAR(20) NOT NULL,
            employee_id VARCHAR(20) NOT NULL,
            filename    VARCHAR(200) NOT NULL,
            captured_at DATETIME    NOT NULL,
            PRIMARY KEY (id),
            INDEX idx_employee_date (employee_id, captured_at),
            INDEX idx_session_id    (session_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
}


def create_tables():
    print("=" * 55)
    print("  Employee Tracker — Database Setup")
    print("=" * 55)
    print(f"\nConnecting to {DB_CONFIG['host']} / {DB_CONFIG['database']} ...")

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
    except MySQLError as e:
        print(f"\n[ERROR] Could not connect: {e}")
        sys.exit(1)

    cursor = conn.cursor()

    for table_name, ddl in TABLES.items():
        try:
            cursor.execute(ddl)
            print(f"  [OK]  {table_name}")
        except MySQLError as e:
            print(f"  [FAIL] {table_name}: {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print("\nDone. All tables are ready.")


if __name__ == "__main__":
    create_tables()

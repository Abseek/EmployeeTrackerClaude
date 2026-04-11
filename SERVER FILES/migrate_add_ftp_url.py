"""
migrate_add_ftp_url.py  —  Run once to add the ftp_url column to screenshots.

Usage:
    python "migrate_add_ftp_url.py"
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


def run():
    print("Connecting to database...")
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
    except MySQLError as e:
        print(f"[ERROR] Could not connect: {e}")
        sys.exit(1)

    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'screenshots' AND COLUMN_NAME = 'ftp_url'
    """, (DB_CONFIG["database"],))
    already_exists = cursor.fetchone()[0] > 0

    if already_exists:
        print("Column 'ftp_url' already exists — nothing to do.")
    else:
        cursor.execute(
            "ALTER TABLE screenshots ADD COLUMN ftp_url VARCHAR(500) DEFAULT NULL"
        )
        conn.commit()
        print("Column 'ftp_url' added to screenshots table successfully.")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    run()

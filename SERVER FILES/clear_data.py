"""
clear_data.py  —  Wipe all data from every table (keeps the schema intact).

WARNING: This operation is irreversible. Use only for periodic cleanup or testing.

Usage:
    pip install mysql-connector-python
    python clear_data.py
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

# Order matters: child tables first (no FK violations when FK checks are off,
# but this order is correct anyway).
TABLES = [
    "activity_buckets",
    "screenshots",
    "sessions",
    "app_settings",
    "accounts",
]


def get_row_counts(cursor) -> dict:
    counts = {}
    for t in TABLES:
        cursor.execute(f"SELECT COUNT(*) FROM `{t}`")
        counts[t] = cursor.fetchone()[0]
    return counts


def clear_all_data():
    print("=" * 55)
    print("  Employee Tracker — Database Cleanup")
    print("=" * 55)
    print(f"\nConnecting to {DB_CONFIG['host']} / {DB_CONFIG['database']} ...")

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
    except MySQLError as e:
        print(f"\n[ERROR] Could not connect: {e}")
        sys.exit(1)

    cursor = conn.cursor()

    print("\nCurrent row counts:")
    counts = get_row_counts(cursor)
    total = 0
    for table, count in counts.items():
        print(f"  {table:<22} {count:>8} rows")
        total += count
    print(f"  {'TOTAL':<22} {total:>8} rows")

    if total == 0:
        print("\nDatabase is already empty. Nothing to do.")
        cursor.close()
        conn.close()
        return

    print("\n" + "!" * 55)
    print("  WARNING: This will permanently delete ALL data.")
    print("!" * 55)
    confirm = input("\nType  YES  to proceed, anything else to cancel: ").strip()

    if confirm != "YES":
        print("\nAborted. No data was changed.")
        cursor.close()
        conn.close()
        return

    print("\nClearing tables ...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

    for table in TABLES:
        try:
            cursor.execute(f"TRUNCATE TABLE `{table}`")
            print(f"  [CLEARED]  {table}")
        except MySQLError as e:
            print(f"  [FAILED]   {table}: {e}")

    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    cursor.close()
    conn.close()

    print("\nAll data has been removed. Schema and tables are intact.")


if __name__ == "__main__":
    clear_all_data()

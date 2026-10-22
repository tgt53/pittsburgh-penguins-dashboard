"""List tables and inspect the Penguins player-impact table without changing data."""

import os
import ssl
from urllib.parse import unquote, urlparse

import certifi
import pymysql

import load_moneypuck_to_tidb as loader


TARGET_TABLE = "penguins_player_impact_2025_26"


def main():
    # Reuse the loader's local .env reader so the database URL stays out of this script.
    loader.read_local_env()
    connection_url = os.environ.get("TIDB_URL")
    if not connection_url:
        raise SystemExit("Add TIDB_URL to your local .env file before running this script.")

    parsed = urlparse(connection_url)
    if parsed.scheme != "mysql" or not parsed.hostname or not parsed.username or not parsed.password:
        raise SystemExit("TIDB_URL must be a complete mysql:// connection URL.")
    database = parsed.path.strip("/")
    if not database:
        raise SystemExit("TIDB_URL must include the database name in its path.")

    connection = pymysql.connect(
        host=parsed.hostname,
        port=parsed.port or 3306,
        user=unquote(parsed.username),
        password=unquote(parsed.password),
        database=database,
        ssl=ssl.create_default_context(cafile=certifi.where()),
        connect_timeout=20,
        read_timeout=60,
        charset="utf8mb4",
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"Tables in `{database}`:")
            for table in tables:
                print(f"- {table}")

            if TARGET_TABLE not in tables:
                print(f"\n`{TARGET_TABLE}` was not found in `{database}`.")
                return

            cursor.execute(f"SHOW COLUMNS FROM `{TARGET_TABLE}`")
            columns = [row[0] for row in cursor.fetchall()]
            print(f"\nColumns in `{TARGET_TABLE}`:")
            for column in columns:
                print(f"- {column}")

            cursor.execute(f"SELECT * FROM `{TARGET_TABLE}` LIMIT 3")
            row_columns = [description[0] for description in cursor.description]
            print(f"\nFirst 3 rows from `{TARGET_TABLE}`:")
            for row in cursor.fetchall():
                print(dict(zip(row_columns, row)))
    finally:
        connection.close()


if __name__ == "__main__":
    main()

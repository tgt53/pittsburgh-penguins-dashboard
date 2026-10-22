"""Create the project's MySQL-compatible database connection."""

import os
import ssl
from pathlib import Path
from urllib.parse import unquote, urlparse

import certifi
import pymysql


PROJECT_DIR = Path(__file__).resolve().parents[1]


def _load_local_env():
    env_path = PROJECT_DIR / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_db_connection():
    _load_local_env()
    connection_url = os.environ.get("TIDB_URL")
    if not connection_url:
        raise RuntimeError("Add TIDB_URL to your local .env file before connecting to the database.")

    parsed = urlparse(connection_url)
    database = parsed.path.strip("/")
    if parsed.scheme != "mysql" or not parsed.hostname or not parsed.username or not parsed.password or not database:
        raise RuntimeError("TIDB_URL must be a complete mysql:// connection URL with a database path.")

    return pymysql.connect(
        host=parsed.hostname,
        port=parsed.port or 3306,
        user=unquote(parsed.username),
        password=unquote(parsed.password),
        database=database,
        ssl=ssl.create_default_context(cafile=certifi.where()),
        connect_timeout=20,
        read_timeout=60,
        write_timeout=60,
        charset="utf8mb4",
    )

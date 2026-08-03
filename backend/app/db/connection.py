import sqlite3
from pathlib import Path

from app.config import DB_PATH, ensure_dirs

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    ensure_dirs()
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def fresh_database(db_path: Path | None = None) -> sqlite3.Connection:
    """Delete any existing working database and recreate it from schema.sql.
    Never touches source export files - only the local working DB."""
    ensure_dirs()
    path = db_path or DB_PATH
    if path.exists():
        path.unlink()
    conn = get_connection(path)
    init_schema(conn)
    return conn

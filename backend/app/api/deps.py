import sqlite3
from collections.abc import Generator

from app.config import DB_PATH


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")  # API is read-only; edits go through the review/approve flow
    try:
        yield conn
    finally:
        conn.close()

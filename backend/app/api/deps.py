import sqlite3
from collections.abc import Generator

from app.config import DB_PATH


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")  # read-only by default; edits go through get_db_writable
    try:
        yield conn
    finally:
        conn.close()


def get_db_writable() -> Generator[sqlite3.Connection, None, None]:
    """Only for the composite-group review endpoints (approve/reject) - the
    one place this local-first API is allowed to write, since it's purely
    a human review decision over data already on disk, not an edit to the
    timetable itself."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()

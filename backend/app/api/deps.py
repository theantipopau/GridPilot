import sqlite3
from collections.abc import Generator

from app.config import DB_PATH


def get_db() -> Generator[sqlite3.Connection, None, None]:
    # check_same_thread=False: FastAPI runs a sync generator dependency's
    # setup (before yield) and teardown (after yield, in `finally`) as
    # separate thread-pool work items, with no guaranteed thread affinity
    # between them - sqlite3's default same-thread check trips on close()
    # even though the connection is never actually used concurrently
    # across requests. Safe here because each request gets its own
    # connection, opened and closed within that single request's lifecycle.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")  # read-only by default; edits go through get_db_writable
    try:
        yield conn
    finally:
        conn.close()


def get_db_writable() -> Generator[sqlite3.Connection, None, None]:
    """Only for the composite-group review and change-set endpoints - the
    only places this local-first API writes, and only to review/proposal
    data, never to the imported timetable_entry rows themselves."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()

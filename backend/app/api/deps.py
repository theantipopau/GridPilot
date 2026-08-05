import sqlite3
from collections.abc import Generator

from fastapi import HTTPException

from app.config import DB_PATH


def _require_schema_initialized(conn: sqlite3.Connection) -> None:
    """sqlite3.connect() silently creates an empty file at DB_PATH if none
    exists yet - so on a machine that's never run an ingest (see
    app/api/ingest.py's browser upload flow), every endpoint would
    otherwise fail with an unhelpful 'no such table' 500 the moment
    anything connects, including a plain status check. A clear 503 here
    means the frontend's error state reads as 'nothing imported yet', not
    'the backend is broken'."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'timetable_entry'"
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=503, detail="No data has been imported yet - use Import to load a .tfx file.")


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
        _require_schema_initialized(conn)
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
        _require_schema_initialized(conn)
        yield conn
    finally:
        conn.close()

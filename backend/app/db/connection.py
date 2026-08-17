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
    _migrate(conn)
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    """CREATE TABLE IF NOT EXISTS (above) only picks up brand-new tables -
    it's a no-op against a table that already exists, so a column added to
    an existing table needs an explicit, idempotent ALTER TABLE here."""
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(finding)")}
    for column in ("reviewed_at", "reviewed_by", "review_note"):
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE finding ADD COLUMN {column} TEXT")

    # agreement_load_rule predates contact_entry_types (docs/roadmap-v2.md
    # 0.2) by one commit - PRAGMA table_info on a table that doesn't exist
    # yet returns no rows rather than erroring, so this is safe to run
    # unconditionally even before industrial_agreement's first ingest.
    load_rule_columns = {row["name"] for row in conn.execute("PRAGMA table_info(agreement_load_rule)")}
    if load_rule_columns and "contact_entry_types" not in load_rule_columns:
        conn.execute("ALTER TABLE agreement_load_rule ADD COLUMN contact_entry_types TEXT")


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

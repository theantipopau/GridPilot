"""Tests app/db/connection.py's _migrate() - the idempotent ALTER TABLE
path for columns added to a table that already exists in an older
database (CREATE TABLE IF NOT EXISTS alone only picks up brand-new
tables). Exercises the exact real-upgrade scenario this project hit
while building docs/roadmap-v2.md 0.2: agreement_load_rule existed
(from the previous commit) without contact_entry_types."""

import sqlite3

from app.db.connection import SCHEMA_PATH, init_schema


def test_contact_entry_types_column_is_added_to_a_pre_existing_table():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    # Simulate a database created before contact_entry_types existed:
    # drop and recreate agreement_load_rule in its old shape.
    conn.execute("DROP TABLE agreement_load_rule")
    conn.execute(
        """
        CREATE TABLE agreement_load_rule (
            id INTEGER PRIMARY KEY,
            agreement_id INTEGER NOT NULL REFERENCES industrial_agreement(id),
            sector TEXT NOT NULL,
            ordinary_hours_per_week REAL NOT NULL,
            max_contact_hours_per_week REAL NOT NULL,
            prep_correction_pct REAL,
            max_cover_periods_per_year INTEGER,
            clause_reference TEXT,
            UNIQUE (agreement_id, sector)
        )
        """
    )
    conn.commit()
    columns_before = {row["name"] for row in conn.execute("PRAGMA table_info(agreement_load_rule)")}
    assert "contact_entry_types" not in columns_before

    init_schema(conn)  # the real upgrade path - CREATE TABLE IF NOT EXISTS + _migrate()

    columns_after = {row["name"] for row in conn.execute("PRAGMA table_info(agreement_load_rule)")}
    assert "contact_entry_types" in columns_after

    # Idempotent - running it again must not error.
    init_schema(conn)


def test_fresh_database_already_has_the_column_via_create_table():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(agreement_load_rule)")}
    assert "contact_entry_types" in columns


def test_subject_year_level_columns_are_added_to_a_pre_existing_table():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    conn.execute("DROP TABLE subject")
    conn.execute(
        "CREATE TABLE subject (id INTEGER PRIMARY KEY, source_code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, "
        "faculty_id INTEGER REFERENCES faculty(id))"
    )
    conn.execute("INSERT INTO subject (source_code, name) VALUES ('SUBA', 'Subject A')")
    conn.commit()
    columns_before = {row["name"] for row in conn.execute("PRAGMA table_info(subject)")}
    assert "minimum_year_level" not in columns_before

    init_schema(conn)

    columns_after = {row["name"] for row in conn.execute("PRAGMA table_info(subject)")}
    assert {"minimum_year_level", "maximum_year_level"} <= columns_after
    # The existing row survived the migration (ALTER TABLE ADD COLUMN, not a rebuild).
    assert conn.execute("SELECT source_code FROM subject").fetchone()["source_code"] == "SUBA"

    init_schema(conn)  # idempotent

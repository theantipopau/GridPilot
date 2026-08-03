"""Ingestion smoke test against the real Timetabling Solutions export.
Skips if the source folder isn't present (e.g. CI without the real data).
Only asserts on aggregate counts / structure - never prints or asserts on
individual student/teacher names."""

import sqlite3

import pytest

from app.config import TFX_PATH
from app.db.connection import fresh_database
from app.ingest.run import finish_ingest_run, start_ingest_run, table_counts
from app.ingest.tfx_parser import ingest_tfx

pytestmark = pytest.mark.skipif(not TFX_PATH.exists(), reason="real export data not present")


@pytest.fixture()
def ingested_conn(tmp_path) -> sqlite3.Connection:
    db_path = tmp_path / "test.sqlite3"
    conn = fresh_database(db_path)
    run_id = start_ingest_run(conn, str(TFX_PATH))
    ingest_tfx(conn, TFX_PATH, run_id)
    finish_ingest_run(conn, run_id)
    yield conn
    conn.close()


def test_reference_table_counts(ingested_conn):
    counts = table_counts(ingested_conn)
    assert counts["day"] == 10
    assert counts["period"] == 80
    assert counts["room"] == 51
    assert counts["teacher"] == 74
    assert counts["student"] == 560
    assert counts["year_level"] == 6


def test_timetable_entries_cover_full_cycle(ingested_conn):
    count = ingested_conn.execute("SELECT COUNT(*) FROM timetable_entry").fetchone()[0]
    assert count > 2000


def test_every_timetable_entry_has_a_valid_entry_type(ingested_conn):
    rows = ingested_conn.execute(
        "SELECT DISTINCT entry_type FROM timetable_entry"
    ).fetchall()
    seen = {r[0] for r in rows}
    assert seen <= {"LESSON", "BREAK", "ASSEMBLY", "GENERAL_PURPOSE", "DETENTION", "REGISTRATION", "OTHER"}
    assert "LESSON" in seen


def test_no_orphaned_foreign_keys(ingested_conn):
    """PRAGMA foreign_key_check catches any row whose FK doesn't resolve -
    this is the cheapest way to prove the ingester never silently created
    a dangling reference."""
    problems = ingested_conn.execute("PRAGMA foreign_key_check").fetchall()
    assert problems == []


def test_enrolment_derived_from_tfx_alone(ingested_conn):
    count = ingested_conn.execute("SELECT COUNT(*) FROM enrolment").fetchone()[0]
    assert count > 0


def test_room_seats_zero_becomes_null(ingested_conn):
    row = ingested_conn.execute(
        "SELECT COUNT(*) FROM room WHERE seats IS NULL"
    ).fetchone()
    assert row[0] > 0


def test_re_engagement_roll_class_flagged_as_support(ingested_conn):
    row = ingested_conn.execute(
        "SELECT is_support_roll_class FROM roll_class WHERE code = 'RTC'"
    ).fetchone()
    assert row is not None
    assert row[0] == 1


def test_ingest_discrepancies_are_structured_not_silent(ingested_conn):
    """Doesn't assert zero discrepancies (some are expected, e.g. stale
    room overrides) - just that if any exist, they're queryable structured
    records, not swallowed."""
    rows = ingested_conn.execute(
        "SELECT check_name, severity FROM ingest_discrepancy"
    ).fetchall()
    for check_name, severity in rows:
        assert severity in ("info", "warning", "error")
        assert check_name

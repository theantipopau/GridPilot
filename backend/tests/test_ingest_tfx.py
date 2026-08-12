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


# -- Phase A: Settings / MRCGs (blocking lines) / RURs (room pools) --------
# See docs/full-timetabler-plan.md Phase A - these sections were previously
# in KNOWN_UNMODELLED_SECTIONS; parsing them fixed a real bug (see the next
# test) and surfaces the blocking pattern + room-choice constraints.

def test_school_setting_is_parsed_from_the_real_export(ingested_conn):
    row = ingested_conn.execute("SELECT * FROM school_setting").fetchone()
    assert row is not None
    assert row["academic_periods"] == 80
    assert row["teacher_proposed_load_minutes"] == 2580.0
    # Booleans stored as 0/1 - the school's own optimisation preferences,
    # previously invisible to this project.
    assert row["optimise_spread"] == 1
    assert row["max_day_spread"] == 1
    assert row["successive_2_periods"] == 1
    assert row["successive_3_periods"] == 1


def test_no_teacher_has_a_null_contracted_load_after_the_settings_fallback(ingested_conn):
    """The bug this fixed: LoadProposed=0 in the source means 'use the
    school default', not 'no load' - previously became NULL and silently
    dropped 30 of 74 teachers out of teacher_over_contracted_load (WHERE
    contracted_load_minutes IS NOT NULL). See
    docs/full-timetabler-plan.md #4.1."""
    null_count = ingested_conn.execute(
        "SELECT COUNT(*) FROM teacher WHERE contracted_load_minutes IS NULL"
    ).fetchone()[0]
    assert null_count == 0

    covered_by_fallback = ingested_conn.execute(
        "SELECT COUNT(*) FROM teacher WHERE contracted_load_minutes = "
        "(SELECT teacher_proposed_load_minutes FROM school_setting)"
    ).fetchone()[0]
    assert covered_by_fallback == 74  # every real teacher in this export shares the one school default


def test_blocking_lines_match_the_real_mrcg_count(ingested_conn):
    """29 MRCGs in the real .tfx = the option-line / blocking-pattern
    structure (docs/data-formats.md #5.4)."""
    count = ingested_conn.execute("SELECT COUNT(*) FROM blocking_line").fetchone()[0]
    assert count == 29

    named = ingested_conn.execute(
        "SELECT COUNT(*) FROM blocking_line WHERE code = '10ENG'"
    ).fetchone()[0]
    assert named == 1


def test_every_blocking_line_class_group_resolves_with_no_data_loss(ingested_conn):
    """169 = the raw sum of MRCGClassGroups[] across all 29 MRCGs in the
    real file - proves every reference resolved (none silently dropped)."""
    count = ingested_conn.execute("SELECT COUNT(*) FROM blocking_line_class_group").fetchone()[0]
    assert count == 169

    unresolved = ingested_conn.execute(
        "SELECT COUNT(*) FROM ingest_discrepancy WHERE check_name = 'blocking_line_class_group_unresolved'"
    ).fetchone()[0]
    assert unresolved == 0


def test_room_pools_match_the_real_rur_data(ingested_conn):
    """1 RUR in the real .tfx, with 5 rooms and 28 class-name references -
    a room-choice constraint ("one of these classes must use one of these
    rooms")."""
    assert ingested_conn.execute("SELECT COUNT(*) FROM room_pool").fetchone()[0] == 1
    assert ingested_conn.execute("SELECT COUNT(*) FROM room_pool_room").fetchone()[0] == 5
    assert ingested_conn.execute("SELECT COUNT(*) FROM room_pool_class_name").fetchone()[0] == 28

    for check in ("room_pool_room_unresolved", "room_pool_class_name_unresolved"):
        unresolved = ingested_conn.execute(
            "SELECT COUNT(*) FROM ingest_discrepancy WHERE check_name = ?", (check,)
        ).fetchone()[0]
        assert unresolved == 0

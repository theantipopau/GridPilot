"""Tests _ingest_subjects_and_class_names()'s handling of a duplicate
class code - found the hard way against a real, still-under-construction
.tfx export where a rebuilt year level left old ClassNames entries
behind sharing a Code with the live one, under a different ClassNameID.
Previously crashed the whole ingest (sqlite3.IntegrityError: UNIQUE
constraint failed: class_name.code), which - worse - happened after
resync_source_tables() had already committed deleting every source
table, leaving the working database empty (see
app/ingest/run.py's backup/restore fix and test_ingest_run_backup.py).
No real school data - see tests/synthetic.py."""

import sqlite3
from pathlib import Path

from app.ingest.tfx_parser import TfxIngester

SCHEMA_PATH = Path(__file__).parents[1] / "app" / "db" / "schema.sql"


def _bare_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def _ingest_run_id(conn: sqlite3.Connection) -> int:
    cur = conn.execute("INSERT INTO ingest_run (started_at) VALUES ('test')")
    conn.commit()
    return cur.lastrowid


def test_duplicate_class_name_codes_merge_onto_the_first_seen_row_not_crash():
    conn = _bare_conn()
    run_id = _ingest_run_id(conn)
    data = {
        "ClassNames": [
            {"Name": "English2", "Code": "10ENG2", "SubjectName": "English", "SubjectCode": "10ENG",
             "Suffix": "2", "ClassNameID": "{GUID-ORPHAN}"},
            {"Name": "English2", "Code": "10ENG2", "SubjectName": "English", "SubjectCode": "10ENG",
             "Suffix": "2", "ClassNameID": "{GUID-LIVE}"},
        ]
    }
    ingester = TfxIngester(conn, data, run_id)
    ingester._ingest_subjects_and_class_names()

    rows = conn.execute("SELECT * FROM class_name WHERE code = '10ENG2'").fetchall()
    assert len(rows) == 1  # only one row, not a second insert

    kept_id = rows[0]["id"]
    assert ingester.class_name_id_by_source["{GUID-ORPHAN}"] == kept_id
    assert ingester.class_name_id_by_source["{GUID-LIVE}"] == kept_id

    discrepancy = conn.execute(
        "SELECT * FROM ingest_discrepancy WHERE check_name = 'class_name_duplicate_code'"
    ).fetchone()
    assert discrepancy is not None
    assert discrepancy["severity"] == "warning"
    assert "10ENG2" in discrepancy["description"]


def test_distinct_codes_each_get_their_own_row_and_no_discrepancy():
    conn = _bare_conn()
    run_id = _ingest_run_id(conn)
    data = {
        "ClassNames": [
            {"Name": "A", "Code": "07AAA1", "ClassNameID": "{G1}"},
            {"Name": "B", "Code": "07BBB1", "ClassNameID": "{G2}"},
        ]
    }
    ingester = TfxIngester(conn, data, run_id)
    ingester._ingest_subjects_and_class_names()

    assert conn.execute("SELECT COUNT(*) FROM class_name").fetchone()[0] == 2
    assert conn.execute(
        "SELECT COUNT(*) FROM ingest_discrepancy WHERE check_name = 'class_name_duplicate_code'"
    ).fetchone()[0] == 0


def test_a_reference_to_the_orphaned_guid_still_resolves_downstream():
    """The real point of merging onto class_name_id_by_source rather than
    just skipping the duplicate: whichever GUID a later section
    (ClassGroupCourses, RUR references, Timetable entries) actually
    references must still resolve to a valid class_name_id - even the
    'orphaned' one, since which of the two GUIDs ends up referenced
    isn't something this parser can predict in general."""
    conn = _bare_conn()
    run_id = _ingest_run_id(conn)
    data = {
        "ClassNames": [
            {"Name": "English2", "Code": "10ENG2", "ClassNameID": "{GUID-A}"},
            {"Name": "English2", "Code": "10ENG2", "ClassNameID": "{GUID-B}"},
        ]
    }
    ingester = TfxIngester(conn, data, run_id)
    ingester._ingest_subjects_and_class_names()

    resolved_a = ingester.class_name_id_by_source["{GUID-A}"]
    resolved_b = ingester.class_name_id_by_source["{GUID-B}"]
    assert resolved_a == resolved_b
    assert conn.execute("SELECT id FROM class_name WHERE id = ?", (resolved_b,)).fetchone() is not None

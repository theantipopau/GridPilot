"""Tests for Student Options (.sfx) ingestion. Uses a real temp file (like
test_export_real.py's round-trip tests) since ingest_sfx_file reads from
disk, matching the same load-from-path pattern as the .tfx parser. No
real student data - synthetic codes and a fake name (checked for and
rejected) only."""

import json

import pytest

from app.ingest.errors import IngestError
from app.ingest.sfx_parser import ingest_all_sfx, ingest_sfx_file
from tests.synthetic import build_synthetic_db


def _write_sfx(tmp_path, data, name="Test Year.sfx"):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _db_with_ingest_run():
    """sfx_file.ingest_run_id is a required FK - every real ingest run
    creates this row via app.ingest.run.start_ingest_run() before any
    parser touches the database; tests need the same."""
    conn = build_synthetic_db()
    conn.execute("INSERT INTO ingest_run (id, started_at) VALUES (1, 'test')")
    conn.commit()
    return conn


def _minimal_sfx(student_code="100001", include_name=True) -> dict:
    student = {
        "StudentID": "{S1}", "StudentCode": student_code, "YearLevel": "07",
        "StudentPreferences": [
            {"OptionID": "{OPT1}", "ClassID": "{CLS1}"},
            {"OptionID": "{OPT2}", "ClassID": "{CLS2}"},
        ],
    }
    if include_name:
        student["FirstName"] = "Test"
        student["LastName"] = "NotARealStudent"

    return {
        "File ID": "Timetabling Solutions X SO 10.1.1.86",
        "Lines": [{"LineID": "{L1}", "Code": "ELE1", "Name": "Elective Line 1", "Subgrid": 1}],
        "Subjects": [{"SubjectID": "{SUB1}", "Code": "07ART", "Name": "Art", "Units": 1, "ClassSizeMaximum": 25}],
        "Options": [{"OptionID": "{OPT1}", "SubjectID": "{SUB1}", "OptionCode": "07ART", "OptionName": "Art"},
                    {"OptionID": "{OPT2}", "SubjectID": "{SUB1}", "OptionCode": "07MUS", "OptionName": "Music"}],
        "Classes": [{"ClassID": "{CLS1}", "OptionID": "{OPT1}", "LineID": "{L1}", "ClassCode": "07ART1",
                     "SubjectCode": "07ART", "RollClassCode": "7A", "Maximum Class Size": 25},
                    {"ClassID": "{CLS2}", "OptionID": "{OPT2}", "LineID": "{L1}", "ClassCode": "07MUS1",
                     "SubjectCode": "07MUS", "RollClassCode": "7A", "Maximum Class Size": 25}],
        "Students": [student],
        "Constraints": [{"ConstraintID": "{C1}", "TypeStr": "Join", "Note": "", "Limit": 1,
                          "ConstraintOptions": [{"OptionID": "{OPT1}"}, {"OptionID": "{OPT2}"}]}],
    }


def test_ingest_creates_expected_row_counts(tmp_path):
    conn = _db_with_ingest_run()  # has student id=1, code='100001'
    path = _write_sfx(tmp_path, _minimal_sfx())

    result = ingest_sfx_file(conn, path, ingest_run_id=1)

    assert result == {"lines": 1, "subjects": 1, "options": 2, "classes": 2, "preferences": 2, "unlinked_students": 0}
    assert conn.execute("SELECT COUNT(*) FROM sfx_line").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM sfx_subject").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM sfx_option").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM sfx_class").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM sfx_constraint").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM sfx_constraint_option").fetchone()[0] == 2


def test_preference_links_to_existing_student_by_code(tmp_path):
    conn = _db_with_ingest_run()
    path = _write_sfx(tmp_path, _minimal_sfx(student_code="100001"))

    ingest_sfx_file(conn, path, ingest_run_id=1)

    rows = conn.execute(
        "SELECT student_id, student_code, preference_order FROM sfx_student_preference ORDER BY preference_order"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["student_id"] == 1  # the synthetic student's internal id
    assert rows[0]["student_code"] == "100001"
    assert rows[0]["preference_order"] == 1
    assert rows[1]["preference_order"] == 2


def test_unmatched_student_code_is_kept_by_code_with_null_student_id(tmp_path):
    """Expected for planning files covering students not yet in the
    current timetable (e.g. next year's cohort) - must never be dropped
    or raise, just linked by code only."""
    conn = _db_with_ingest_run()
    path = _write_sfx(tmp_path, _minimal_sfx(student_code="999999"))

    result = ingest_sfx_file(conn, path, ingest_run_id=1)

    assert result["unlinked_students"] == 1
    row = conn.execute("SELECT student_id, student_code FROM sfx_student_preference LIMIT 1").fetchone()
    assert row["student_id"] is None
    assert row["student_code"] == "999999"


def test_never_stores_a_student_name_anywhere(tmp_path):
    """Students[].FirstName/LastName are present in the real .sfx files -
    this parser must never copy them into any sfx_* table."""
    conn = _db_with_ingest_run()
    path = _write_sfx(tmp_path, _minimal_sfx(include_name=True))

    ingest_sfx_file(conn, path, ingest_run_id=1)

    sfx_tables = ["sfx_file", "sfx_line", "sfx_subject", "sfx_option", "sfx_class",
                  "sfx_student_preference", "sfx_constraint", "sfx_constraint_option"]
    for table in sfx_tables:
        for row in conn.execute(f"SELECT * FROM {table}"):
            values = " ".join(str(v) for v in row if v is not None)
            assert "NotARealStudent" not in values, f"leaked into {table}"


def test_missing_optional_sections_ingest_as_empty_not_an_error(tmp_path):
    data = _minimal_sfx()
    del data["Constraints"]  # Years 7-9's real files have no Constraints section
    path = _write_sfx(tmp_path, data)
    conn = _db_with_ingest_run()

    result = ingest_sfx_file(conn, path, ingest_run_id=1)

    assert result["preferences"] == 2
    assert conn.execute("SELECT COUNT(*) FROM sfx_constraint").fetchone()[0] == 0


def test_rejects_a_timetable_tfx_file_passed_by_mistake(tmp_path):
    data = _minimal_sfx()
    data["File ID"] = "Timetabling Solutions X TD 10.1.1.86"
    path = _write_sfx(tmp_path, data)
    conn = _db_with_ingest_run()

    with pytest.raises(IngestError, match="timetable"):
        ingest_sfx_file(conn, path, ingest_run_id=1)


def test_ingest_all_sfx_handles_an_empty_list(tmp_path):
    conn = _db_with_ingest_run()
    assert ingest_all_sfx(conn, [], ingest_run_id=1) == {}


def test_ingest_all_sfx_processes_every_file(tmp_path):
    conn = _db_with_ingest_run()
    path_a = _write_sfx(tmp_path, _minimal_sfx(), name="Year A.sfx")
    path_b = _write_sfx(tmp_path, _minimal_sfx(), name="Year B.sfx")

    results = ingest_all_sfx(conn, [path_a, path_b], ingest_run_id=1)

    assert set(results.keys()) == {"Year A.sfx", "Year B.sfx"}
    assert conn.execute("SELECT COUNT(*) FROM sfx_file").fetchone()[0] == 2

"""Cross-validates the .tfx-derived data model against the Timetabling
Solutions CSV exports. This is a validation pass, not a second ingestion
path - the .tfx stays the single source of truth for entity data (see
docs/data-model.md 'Design principles'). Every mismatch is written to
ingest_discrepancy rather than raised/dropped silently, except where a
CSV references a code the .tfx has no record of at all, which is a
genuine "record we can't map" failure per the project's fail-loudly
requirement."""

import csv
import sqlite3
from collections import Counter
from pathlib import Path

from app.ingest.errors import IngestError


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _log(conn: sqlite3.Connection, run_id: int, check_name: str, severity: str, description: str, detail=None) -> None:
    import json
    conn.execute(
        "INSERT INTO ingest_discrepancy (ingest_run_id, check_name, severity, description, detail_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, check_name, severity, description, json.dumps(detail) if detail else None),
    )


def _norm(v) -> str | None:
    v = (v or "").strip()
    return v or None


def validate_rooms(conn: sqlite3.Connection, run_id: int, path: Path) -> None:
    rows = _read_csv(path)
    db_rooms = {r["code"]: r for r in conn.execute("SELECT code, seats, name FROM room")}
    csv_codes = set()
    for row in rows:
        code = row["Room Code"]
        csv_codes.add(code)
        db_row = db_rooms.get(code)
        if db_row is None:
            raise IngestError(f"Room Details.csv has Room Code {code!r} not present in .tfx Rooms[]")
        csv_seats = int(row["Seats"]) or None
        if csv_seats != db_row["seats"]:
            _log(conn, run_id, "room_seats_mismatch", "warning",
                 f"Room {code} seats differ: CSV={row['Seats']} tfx={db_row['seats']}", {"room_code": code})
    missing = set(db_rooms) - csv_codes
    if missing:
        _log(conn, run_id, "room_missing_from_csv", "info",
             f"{len(missing)} room(s) in .tfx not present in Room Details.csv", {"codes": sorted(missing)})


def validate_periods(conn: sqlite3.Connection, run_id: int, path: Path) -> None:
    rows = _read_csv(path)
    db_periods = {(r["day_code"], r["period_no"]): r for r in conn.execute(
        "SELECT p.code AS period_code, p.period_no, d.code AS day_code, p.start_time, p.finish_time "
        "FROM period p JOIN day d ON d.id = p.day_id"
    )}
    for row in rows:
        key = (row["Day Code"], int(row["Period No"]))
        db_row = db_periods.get(key)
        if db_row is None:
            raise IngestError(f"Period Details.csv row {key!r} not present in .tfx Periods[]")
        if db_row["period_code"] != row["Period Code"]:
            _log(conn, run_id, "period_code_mismatch", "warning",
                 f"Period {key} code differs: CSV={row['Period Code']} tfx={db_row['period_code']}", None)


def validate_teachers(conn: sqlite3.Connection, run_id: int, path: Path) -> None:
    rows = _read_csv(path)
    db_teachers = {r["code"]: r for r in conn.execute("SELECT code, email FROM teacher")}
    csv_codes = set()
    for row in rows:
        code = row["Teacher Code"]
        csv_codes.add(code)
        db_row = db_teachers.get(code)
        if db_row is None:
            raise IngestError(f"Teacher Details.csv has Teacher Code {code!r} not present in .tfx Teachers[]")
        if _norm(row["Teacher Email"]) != _norm(db_row["email"]):
            _log(conn, run_id, "teacher_email_mismatch", "warning",
                 f"Teacher {code} email differs between CSV and tfx", {"teacher_code": code})
    missing = set(db_teachers) - csv_codes
    if missing:
        _log(conn, run_id, "teacher_missing_from_csv", "warning",
             f"{len(missing)} teacher(s) in .tfx not present in Teacher Details.csv", {"codes": sorted(missing)})


def validate_roll_classes(conn: sqlite3.Connection, run_id: int, path: Path) -> None:
    rows = _read_csv(path)
    db_roll_classes = {r["code"]: r for r in conn.execute(
        "SELECT rc.code AS code, yl.code AS year_level_code FROM roll_class rc "
        "LEFT JOIN year_level yl ON yl.id = rc.year_level_id"
    )}
    for row in rows:
        code = row["RollClass Level Code"]
        db_row = db_roll_classes.get(code)
        if db_row is None:
            raise IngestError(f"Roll Class Details.csv has code {code!r} not present in .tfx RollClasses[]")
        csv_year = _norm(row["Year Level Code"])
        if csv_year != db_row["year_level_code"]:
            _log(conn, run_id, "roll_class_year_level_mismatch", "warning",
                 f"Roll class {code} year level differs: CSV={csv_year} tfx={db_row['year_level_code']}", None)


def validate_students(conn: sqlite3.Connection, run_id: int, path: Path) -> None:
    rows = _read_csv(path)
    db_students = {r["code"]: r for r in conn.execute(
        "SELECT s.code AS code, rc.code AS roll_class_code FROM student s "
        "LEFT JOIN roll_class rc ON rc.id = s.roll_class_id"
    )}
    csv_codes = set()
    for row in rows:
        code = row["Student Code"]
        csv_codes.add(code)
        db_row = db_students.get(code)
        if db_row is None:
            raise IngestError(f"Student Details.csv has Student Code {code!r} not present in .tfx Students[]")
        if _norm(row["Roll Class"]) != _norm(db_row["roll_class_code"]):
            _log(conn, run_id, "student_roll_class_mismatch", "warning",
                 f"Student {code} roll class differs between CSV and tfx", {"student_code": code})
    missing = set(db_students) - csv_codes
    if missing:
        raise IngestError(
            f"{len(missing)} student(s) present in .tfx but missing from Student Details.csv: {sorted(missing)}"
        )


def _blank_token(v: str) -> str:
    """Master Timetable Cycle.csv writes the literal string '<Blank>' for
    a missing Teacher Code / Room Code (rather than leaving the cell
    empty) in a handful of rows - normalise it to '' to match how the
    .tfx export represents the same 'nothing assigned' state."""
    return "" if v == "<Blank>" else v


def validate_master_timetable(conn: sqlite3.Connection, run_id: int, path: Path) -> None:
    rows = _read_csv(path)
    csv_keys = Counter(
        (r["Day Code"], r["Period Code"], r["Roll Class Code"], r["Class Code"],
         _blank_token(r["Teacher Code"]), _blank_token(r["Room Code"]))
        for r in rows
    )

    db_rows = conn.execute(
        "SELECT d.code AS day_code, p.code AS period_code, rc.code AS roll_class_code, "
        "cn.code AS class_code, t.code AS teacher_code, rm.code AS room_code, te.entry_type "
        "FROM timetable_entry te "
        "JOIN day d ON d.id = te.day_id "
        "JOIN period p ON p.id = te.period_id "
        "JOIN roll_class rc ON rc.id = te.roll_class_id "
        "LEFT JOIN class_name cn ON cn.id = te.class_name_id "
        "LEFT JOIN teacher t ON t.id = te.teacher_id "
        "LEFT JOIN room rm ON rm.id = te.room_id"
    ).fetchall()

    db_keys = Counter()
    unassigned_count = 0
    for r in db_rows:
        if r["class_code"] is None:
            unassigned_count += 1
            continue
        db_keys[(r["day_code"], r["period_code"], r["roll_class_code"], r["class_code"],
                  r["teacher_code"] or "", r["room_code"] or "")] += 1

    only_in_csv = csv_keys - db_keys
    only_in_db = db_keys - csv_keys

    if unassigned_count:
        _log(conn, run_id, "timetable_unassigned_entries_excluded_from_csv", "info",
             f"{unassigned_count} .tfx Timetable[] entries have no ClassNameID assigned and are, as "
             f"expected, absent from Master Timetable Cycle.csv (see docs/data-formats.md #5.5)",
             {"count": unassigned_count})

    if only_in_csv:
        _log(conn, run_id, "timetable_row_only_in_csv", "error",
             f"{sum(only_in_csv.values())} row(s) in Master Timetable Cycle.csv have no matching .tfx "
             f"Timetable[] entry", {"sample": list(only_in_csv)[:10]})

    unexplained_db_only = sum(only_in_db.values()) - unassigned_count
    if unexplained_db_only > 0:
        _log(conn, run_id, "timetable_row_only_in_tfx_unexplained", "warning",
             f"{unexplained_db_only} .tfx timetable row(s) with an assigned class have no matching row "
             f"in Master Timetable Cycle.csv", {"sample": list(only_in_db)[:10]})


def run_all_validations(conn: sqlite3.Connection, run_id: int, paths: dict) -> None:
    validate_rooms(conn, run_id, paths["rooms"])
    validate_periods(conn, run_id, paths["periods"])
    validate_teachers(conn, run_id, paths["teachers"])
    validate_roll_classes(conn, run_id, paths["roll_classes"])
    validate_students(conn, run_id, paths["students"])
    validate_master_timetable(conn, run_id, paths["master_timetable"])
    conn.commit()

"""Shared what-if machinery: apply a hypothetical override to a copy of
the timetable entries and re-run the clash rules against it, without
ever touching the database. Used by both change-set validation
(app/changes/service.py) and the suggestion engine (app/analysis/
suggestions.py) - one implementation, not two copies that could drift."""

import sqlite3

from app.analysis.clash_rules import room_double_booking, student_double_booking, teacher_double_booking
from app.analysis.composite_review import ApprovedComposites
from app.analysis.models import Finding


def apply_overrides(entries: list[dict], overrides: dict[int, dict], code_lookups: dict) -> list[dict]:
    """overrides: entry_id -> {after_day_id, after_period_id, after_room_id, after_teacher_id}
    (any key omitted or None leaves that field unchanged)."""
    modified = []
    for e in entries:
        change = overrides.get(e["entry_id"])
        if change is None:
            modified.append(e)
            continue
        new_entry = dict(e)
        if change.get("after_day_id") is not None:
            new_entry["day_id"] = change["after_day_id"]
            new_entry["day_code"] = code_lookups["day"][change["after_day_id"]]
        if change.get("after_period_id") is not None:
            new_entry["period_id"] = change["after_period_id"]
            new_entry["period_code"] = code_lookups["period"][change["after_period_id"]]
        if "after_room_id" in change:
            new_entry["room_id"] = change["after_room_id"]
            new_entry["room_code"] = code_lookups["room"].get(change["after_room_id"])
        if "after_teacher_id" in change:
            new_entry["teacher_id"] = change["after_teacher_id"]
            new_entry["teacher_code"] = code_lookups["teacher"].get(change["after_teacher_id"])
        modified.append(new_entry)
    return modified


def run_clash_findings(conn: sqlite3.Connection, entries: list[dict], composites: ApprovedComposites) -> list[Finding]:
    return [
        *teacher_double_booking(entries, composites),
        *room_double_booking(entries, composites),
        *student_double_booking(conn, entries, composites),
    ]


def load_code_lookups(conn: sqlite3.Connection) -> dict:
    return {
        "day": {r["id"]: r["code"] for r in conn.execute("SELECT id, code FROM day")},
        "period": {r["id"]: r["code"] for r in conn.execute("SELECT id, code FROM period")},
        "room": {r["id"]: r["code"] for r in conn.execute("SELECT id, code FROM room")},
        "teacher": {r["id"]: r["code"] for r in conn.execute("SELECT id, code FROM teacher")},
    }

"""The export gate (PROJECT_ROADMAP.md Milestone 6): turn an APPROVED
change set into a re-importable .tfx file.

Strategy: patch, never rebuild. The original .tfx is loaded as plain
JSON and only the specific Timetable[] entries an approved change
touches are mutated in place (found via timetable_entry.source_ref,
which is exactly "tfx:Timetable[<index>]" - see app/ingest/tfx_parser.py).
Every other byte of the structure - every other array, every untouched
Timetable[] entry - is left completely alone. This is what makes the
"unchanged-record fidelity" and "structural comparison" gates trivially
provable rather than something we have to carefully reconstruct: we
never touch those records, so they can't have changed.

Nothing here writes a file by itself - see app/export/run.py, which is
the only place a file actually gets written, and only behind an explicit
--confirm flag (PROJECT_ROADMAP.md: "keep export behind an experimental
flag")."""

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

SOURCE_REF_PATTERN = re.compile(r"^tfx:Timetable\[(\d+)\]$")


class ExportError(Exception):
    pass


def load_source_json(path: Path) -> dict:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def build_reverse_lookups(conn: sqlite3.Connection) -> dict:
    return {
        "period": {r["id"]: r["source_guid"] for r in conn.execute("SELECT id, source_guid FROM period")},
        "room": {r["id"]: r["source_guid"] for r in conn.execute("SELECT id, source_guid FROM room")},
        "teacher": {r["id"]: r["source_guid"] for r in conn.execute("SELECT id, source_guid FROM teacher")},
    }


def get_approved_change_set(conn: sqlite3.Connection, change_set_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM change_set WHERE id = ?", (change_set_id,)).fetchone()
    if row is None:
        raise ExportError(f"No change set {change_set_id}")
    if row["approval_status"] != "APPROVED":
        raise ExportError(f"Change set {change_set_id} is {row['approval_status']}, not APPROVED - cannot export")
    return row


def get_changes_with_source_ref(conn: sqlite3.Connection, change_set_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT pc.*, te.source_ref
        FROM proposed_change pc
        JOIN timetable_entry te ON te.id = pc.timetable_entry_id
        WHERE pc.change_set_id = ?
        ORDER BY pc.id
        """,
        (change_set_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _entry_index(source_ref: str) -> int:
    m = SOURCE_REF_PATTERN.match(source_ref)
    if not m:
        raise ExportError(
            f"timetable_entry.source_ref {source_ref!r} doesn't match the expected tfx:Timetable[N] "
            "shape - can't map it back to a raw .tfx array position."
        )
    return int(m.group(1))


@dataclass
class ChangelogEntry:
    proposed_change_id: int
    timetable_index: int
    before: dict
    after: dict


def apply_change_set(data: dict, changes: list[dict], reverse_lookups: dict) -> tuple[dict, list[ChangelogEntry]]:
    """Returns a new dict (the input is never mutated) and the changelog.
    Raises ExportError if any change references a room/teacher/period that
    no longer has a source GUID (would produce an invalid .tfx)."""
    patched = json.loads(json.dumps(data))  # deep copy via round-trip, not by reference
    changelog = []

    for change in changes:
        idx = _entry_index(change["source_ref"])
        if idx >= len(patched["Timetable"]):
            raise ExportError(f"source_ref index {idx} is out of range for this .tfx's Timetable[] array")

        entry = patched["Timetable"][idx]
        before = dict(entry)

        period_guid = reverse_lookups["period"].get(change["after_period_id"])
        if period_guid is None:
            raise ExportError(f"No source GUID for period id {change['after_period_id']}")
        entry["PeriodID"] = period_guid

        if change["after_room_id"] is not None:
            room_guid = reverse_lookups["room"].get(change["after_room_id"])
            if room_guid is None:
                raise ExportError(f"No source GUID for room id {change['after_room_id']}")
            entry["RoomID"] = room_guid
        else:
            entry["RoomID"] = ""

        if change["after_teacher_id"] is not None:
            teacher_guid = reverse_lookups["teacher"].get(change["after_teacher_id"])
            if teacher_guid is None:
                raise ExportError(f"No source GUID for teacher id {change['after_teacher_id']}")
            entry["TeacherID"] = teacher_guid
        else:
            entry["TeacherID"] = ""

        changelog.append(ChangelogEntry(change["id"], idx, before, dict(entry)))

    return patched, changelog

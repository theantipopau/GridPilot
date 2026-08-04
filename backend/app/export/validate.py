"""The export gate's validation checks, per PROJECT_ROADMAP.md Milestone 6.
An export is not "ready" unless every gate here passes. The strongest
gate (`round_trip_reparse`) doesn't trust the in-memory patch at all -
it writes the patched JSON to a real temp file and re-ingests it through
the application's own production parser (app.ingest.tfx_parser), the
same code path that ingests the real export, then re-runs the same
clash rules used everywhere else in the app. That's the actual proof
that what gets written is something this application (and, by the same
logic, Timetabling Solutions) can read back correctly."""

import json
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.analysis.clash_rules import run_clash_rules
from app.db.connection import fresh_database
from app.export.tfx_writer import ChangelogEntry
from app.ingest.errors import IngestError
from app.ingest.run import start_ingest_run, ingest_tfx as _ingest_tfx_step


@dataclass
class GateResult:
    passed: bool
    detail: dict = field(default_factory=dict)


@dataclass
class ValidationReport:
    ready: bool
    gates: dict[str, GateResult]
    changelog: list[dict]


def _gate_structural_comparison(original: dict, patched: dict) -> GateResult:
    if set(original.keys()) != set(patched.keys()):
        return GateResult(False, {"reason": "top-level key sets differ",
                                   "only_in_original": sorted(set(original) - set(patched)),
                                   "only_in_patched": sorted(set(patched) - set(original))})
    mismatches = {}
    for key, value in original.items():
        if isinstance(value, list) and len(value) != len(patched[key]):
            mismatches[key] = {"original_length": len(value), "patched_length": len(patched[key])}
    if mismatches:
        return GateResult(False, {"reason": "array length(s) changed", "mismatches": mismatches})
    return GateResult(True)


def _gate_unchanged_record_fidelity(original: dict, patched: dict, touched_indices: set[int]) -> GateResult:
    for key, value in original.items():
        if key == "Timetable":
            continue
        if patched[key] != value:
            return GateResult(False, {"reason": f"top-level key {key!r} changed but should never have been touched"})

    diffs = []
    for i, (before, after) in enumerate(zip(original["Timetable"], patched["Timetable"])):
        if i in touched_indices:
            continue
        if before != after:
            diffs.append(i)
    if diffs:
        return GateResult(False, {"reason": "untouched Timetable[] entries changed", "indices": diffs})
    return GateResult(True)


def _gate_referential_integrity(patched: dict, touched_indices: set[int]) -> GateResult:
    period_ids = {p["PeriodID"] for p in patched.get("Periods", [])}
    room_ids = {r["RoomID"] for r in patched.get("Rooms", [])}
    teacher_ids = {t["TeacherID"] for t in patched.get("Teachers", [])}

    problems = []
    for i in touched_indices:
        entry = patched["Timetable"][i]
        if entry["PeriodID"] not in period_ids:
            problems.append({"index": i, "field": "PeriodID", "value": entry["PeriodID"]})
        if entry["RoomID"] and entry["RoomID"] not in room_ids:
            problems.append({"index": i, "field": "RoomID", "value": entry["RoomID"]})
        if entry["TeacherID"] and entry["TeacherID"] not in teacher_ids:
            problems.append({"index": i, "field": "TeacherID", "value": entry["TeacherID"]})
    if problems:
        return GateResult(False, {"problems": problems})
    return GateResult(True)


def _gate_json_round_trip(patched: dict) -> GateResult:
    try:
        reparsed = json.loads(json.dumps(patched))
    except (TypeError, ValueError) as e:
        return GateResult(False, {"reason": str(e)})
    if reparsed != patched:
        return GateResult(False, {"reason": "value changed shape across a JSON serialise/parse round-trip"})
    return GateResult(True)


def _copy_composite_review_state(conn: sqlite3.Connection, temp_conn: sqlite3.Connection) -> None:
    """The freshly re-ingested temp DB has no composite_group rows (that's
    human review data, not derived from the .tfx) - copy the real
    database's review decisions across so the clash-rule comparison is
    fair (an approved composite must stay suppressed in the re-ingested
    copy too, the same as it is in the real working database)."""
    groups = conn.execute(
        "SELECT id, teacher_id, room_id, review_status, slot_count, detected_at, reviewed_at, reviewed_by, review_note "
        "FROM composite_group"
    ).fetchall()
    teacher_code_by_id = {r["id"]: r["code"] for r in conn.execute("SELECT id, code FROM teacher")}
    room_code_by_id = {r["id"]: r["code"] for r in conn.execute("SELECT id, code FROM room")}
    class_code_by_id = {r["id"]: r["code"] for r in conn.execute("SELECT id, code FROM class_name")}

    temp_teacher_id_by_code = {r["code"]: r["id"] for r in temp_conn.execute("SELECT id, code FROM teacher")}
    temp_room_id_by_code = {r["code"]: r["id"] for r in temp_conn.execute("SELECT id, code FROM room")}
    temp_class_id_by_code = {r["code"]: r["id"] for r in temp_conn.execute("SELECT id, code FROM class_name")}

    members_by_group: dict[int, list[int]] = {}
    for m in conn.execute("SELECT composite_group_id, class_name_id FROM composite_group_member"):
        members_by_group.setdefault(m["composite_group_id"], []).append(m["class_name_id"])

    # A (teacher, room) pair can host several distinct composite groups
    # (seen in the real data - a shared study room with rotating
    # supervisors) - identify each group by its full member-class-code
    # set, not just teacher+room, so groups are never conflated.
    for g in groups:
        teacher_code = teacher_code_by_id.get(g["teacher_id"])
        room_code = room_code_by_id.get(g["room_id"])
        new_teacher_id = temp_teacher_id_by_code.get(teacher_code)
        new_room_id = temp_room_id_by_code.get(room_code)
        if new_teacher_id is None or new_room_id is None:
            continue

        member_codes = [class_code_by_id.get(cid) for cid in members_by_group.get(g["id"], [])]
        new_member_ids = [temp_class_id_by_code[c] for c in member_codes if c in temp_class_id_by_code]
        if not new_member_ids:
            continue

        cur = temp_conn.execute(
            "INSERT INTO composite_group (teacher_id, room_id, review_status, slot_count, detected_at, "
            "reviewed_at, reviewed_by, review_note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (new_teacher_id, new_room_id, g["review_status"], g["slot_count"], g["detected_at"],
             g["reviewed_at"], g["reviewed_by"], g["review_note"]),
        )
        new_group_id = cur.lastrowid
        temp_conn.executemany(
            "INSERT OR IGNORE INTO composite_group_member (composite_group_id, class_name_id) VALUES (?, ?)",
            [(new_group_id, cid) for cid in new_member_ids],
        )
    temp_conn.commit()


def _gate_round_trip_reparse(
    conn: sqlite3.Connection, patched: dict, changes: list[dict], changelog: list[ChangelogEntry]
) -> tuple[GateResult, GateResult]:
    """Returns (reconciliation_gate, no_new_clashes_gate). Writes the
    patched JSON to a real temp file and re-ingests it with the
    application's own production parser - the strongest proof available
    that the output is well-formed and semantically correct, short of
    actually re-importing it into Timetabling Solutions itself (which
    this tool has no way to drive - see docs/export-validation.md)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_tfx = Path(tmp) / "export_candidate.tfx"
        tmp_tfx.write_text(json.dumps(patched), encoding="utf-8")
        tmp_db = Path(tmp) / "reparse_check.sqlite3"

        temp_conn = fresh_database(tmp_db)
        try:
            try:
                run_id = start_ingest_run(temp_conn, str(tmp_tfx))
                _ingest_tfx_step(temp_conn, tmp_tfx, run_id)
            except IngestError as e:
                error = GateResult(False, {"reason": f"application's own parser rejected the exported file: {e}"})
                return error, error

            _copy_composite_review_state(conn, temp_conn)

            # Reconciliation: every proposed change's after-values must
            # show up exactly, for the matching entry, in the re-ingested copy.
            reconciliation_problems = []
            for change, entry in zip(changes, changelog):
                row = temp_conn.execute(
                    """
                    SELECT d.code AS day_code, p.code AS period_code, rm.code AS room_code, t.code AS teacher_code
                    FROM timetable_entry te
                    JOIN day d ON d.id = te.day_id
                    JOIN period p ON p.id = te.period_id
                    LEFT JOIN room rm ON rm.id = te.room_id
                    LEFT JOIN teacher t ON t.id = te.teacher_id
                    WHERE te.source_ref = ?
                    """,
                    (f"tfx:Timetable[{entry.timetable_index}]",),
                ).fetchone()
                expected_room = conn.execute(
                    "SELECT code FROM room WHERE id = ?", (change["after_room_id"],)
                ).fetchone()
                expected_teacher = conn.execute(
                    "SELECT code FROM teacher WHERE id = ?", (change["after_teacher_id"],)
                ).fetchone()
                expected_period = conn.execute(
                    "SELECT p.code FROM period p WHERE p.id = ?", (change["after_period_id"],)
                ).fetchone()
                if row is None:
                    reconciliation_problems.append(
                        {"proposed_change_id": change["id"], "reason": "entry not found after re-ingest"}
                    )
                    continue
                if row["period_code"] != (expected_period["code"] if expected_period else None):
                    reconciliation_problems.append({"proposed_change_id": change["id"], "field": "period",
                                                     "expected": expected_period["code"] if expected_period else None,
                                                     "actual": row["period_code"]})
                if row["room_code"] != (expected_room["code"] if expected_room else None):
                    reconciliation_problems.append({"proposed_change_id": change["id"], "field": "room",
                                                     "expected": expected_room["code"] if expected_room else None,
                                                     "actual": row["room_code"]})
                if row["teacher_code"] != (expected_teacher["code"] if expected_teacher else None):
                    reconciliation_problems.append({"proposed_change_id": change["id"], "field": "teacher",
                                                     "expected": expected_teacher["code"] if expected_teacher else None,
                                                     "actual": row["teacher_code"]})

            reconciliation = GateResult(len(reconciliation_problems) == 0, {"problems": reconciliation_problems})

            # No new clashes: compare the current working DB's findings
            # against the re-ingested-and-exported copy's findings.
            before_keys = {f.dedupe_key() for f in run_clash_rules(conn)}
            after_keys = {f.dedupe_key() for f in run_clash_rules(temp_conn)}
            introduced = after_keys - before_keys
            no_new_clashes = GateResult(len(introduced) == 0, {"introduced_count": len(introduced)})
        finally:
            temp_conn.close()

    return reconciliation, no_new_clashes


def validate_export(conn: sqlite3.Connection, change_set_id: int, original: dict, patched: dict,
                     changes: list[dict], changelog: list[ChangelogEntry]) -> ValidationReport:
    touched_indices = {e.timetable_index for e in changelog}

    gates: dict[str, GateResult] = {}
    gates["json_round_trip"] = _gate_json_round_trip(patched)
    gates["structural_comparison"] = _gate_structural_comparison(original, patched)
    gates["unchanged_record_fidelity"] = _gate_unchanged_record_fidelity(original, patched, touched_indices)
    gates["referential_integrity"] = _gate_referential_integrity(patched, touched_indices)

    reconciliation, no_new_clashes = _gate_round_trip_reparse(conn, patched, changes, changelog)
    gates["change_set_reconciliation"] = reconciliation
    gates["no_new_clashes"] = no_new_clashes

    ready = all(g.passed for g in gates.values())
    changelog_dicts = [
        {"proposed_change_id": e.proposed_change_id, "timetable_index": e.timetable_index,
         "before": e.before, "after": e.after}
        for e in changelog
    ]
    return ValidationReport(ready=ready, gates=gates, changelog=changelog_dicts)

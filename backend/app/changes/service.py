"""Safe change sets, per PROJECT_ROADMAP.md Milestone 3: proposed edits
are represented entirely separately from the imported timetable_entry
rows. Approving a change set never mutates timetable_entry - the
change_set/proposed_change rows themselves are the durable record of the
approved edit (a future export step, not built yet, is what would turn
an approved change set into a re-importable file).

Validation is a what-if re-run of the clash rules against an in-memory
copy of the timetable with the proposed changes applied - never a real
write. See validate_change_set()."""

import datetime as dt
import json
import sqlite3

from app.analysis.clash_rules import lesson_entries
from app.analysis.composite_review import load_approved_composites
from app.analysis.models import Finding
from app.analysis.whatif import apply_overrides, load_code_lookups, run_clash_findings


class ChangeSetError(Exception):
    pass


def create_change_set(conn: sqlite3.Connection, name: str, description: str | None, created_by: str) -> int:
    now = dt.datetime.now(dt.UTC).isoformat()
    cur = conn.execute(
        "INSERT INTO change_set (name, description, created_at, created_by) VALUES (?, ?, ?, ?)",
        (name, description, now, created_by),
    )
    conn.commit()
    return cur.lastrowid


def _require_draft(conn: sqlite3.Connection, change_set_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM change_set WHERE id = ?", (change_set_id,)).fetchone()
    if row is None:
        raise ChangeSetError(f"No change set {change_set_id}")
    if row["approval_status"] != "DRAFT":
        raise ChangeSetError(f"Change set {change_set_id} is {row['approval_status']}, not editable")
    return row


def add_proposed_change(
    conn: sqlite3.Connection,
    change_set_id: int,
    timetable_entry_id: int,
    *,
    after_day_id: int | None = None,
    after_period_id: int | None = None,
    after_room_id: int | None = None,
    after_teacher_id: int | None = None,
    reason: str | None = None,
    finding_ids: list[int] | None = None,
) -> int:
    _require_draft(conn, change_set_id)

    entry = conn.execute(
        "SELECT day_id, period_id, room_id, teacher_id FROM timetable_entry WHERE id = ?",
        (timetable_entry_id,),
    ).fetchone()
    if entry is None:
        raise ChangeSetError(f"No timetable_entry {timetable_entry_id}")

    cur = conn.execute(
        "INSERT INTO proposed_change (change_set_id, timetable_entry_id, before_day_id, before_period_id, "
        "before_room_id, before_teacher_id, after_day_id, after_period_id, after_room_id, after_teacher_id, reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            change_set_id, timetable_entry_id,
            entry["day_id"], entry["period_id"], entry["room_id"], entry["teacher_id"],
            after_day_id if after_day_id is not None else entry["day_id"],
            after_period_id if after_period_id is not None else entry["period_id"],
            after_room_id if after_room_id is not None else entry["room_id"],
            after_teacher_id if after_teacher_id is not None else entry["teacher_id"],
            reason,
        ),
    )
    proposed_change_id = cur.lastrowid

    for finding_id in finding_ids or []:
        conn.execute(
            "INSERT OR IGNORE INTO proposed_change_finding (proposed_change_id, finding_id) VALUES (?, ?)",
            (proposed_change_id, finding_id),
        )

    conn.execute(
        "UPDATE change_set SET validation_status = 'NOT_VALIDATED', validation_result_json = NULL WHERE id = ?",
        (change_set_id,),
    )
    conn.commit()
    return proposed_change_id


def remove_proposed_change(conn: sqlite3.Connection, change_set_id: int, proposed_change_id: int) -> None:
    _require_draft(conn, change_set_id)
    conn.execute("DELETE FROM proposed_change_finding WHERE proposed_change_id = ?", (proposed_change_id,))
    conn.execute(
        "DELETE FROM proposed_change WHERE id = ? AND change_set_id = ?", (proposed_change_id, change_set_id)
    )
    conn.execute(
        "UPDATE change_set SET validation_status = 'NOT_VALIDATED', validation_result_json = NULL WHERE id = ?",
        (change_set_id,),
    )
    conn.commit()


def validate_change_set(conn: sqlite3.Connection, change_set_id: int) -> dict:
    change_set = conn.execute("SELECT * FROM change_set WHERE id = ?", (change_set_id,)).fetchone()
    if change_set is None:
        raise ChangeSetError(f"No change set {change_set_id}")

    changes = conn.execute(
        "SELECT * FROM proposed_change WHERE change_set_id = ?", (change_set_id,)
    ).fetchall()
    if not changes:
        result = {"valid": False, "reason": "Change set has no proposed changes.", "introduced_findings": [],
                   "resolved_findings": [], "unresolved_originating_findings": []}
        _store_validation(conn, change_set_id, result)
        return result

    code_lookups = load_code_lookups(conn)
    overrides = {
        c["timetable_entry_id"]: {
            "after_day_id": c["after_day_id"], "after_period_id": c["after_period_id"],
            "after_room_id": c["after_room_id"], "after_teacher_id": c["after_teacher_id"],
        }
        for c in changes
    }

    before_entries = lesson_entries(conn)
    after_entries = apply_overrides(before_entries, overrides, code_lookups)

    composites = load_approved_composites(conn)
    before_findings = {f.dedupe_key(): f for f in run_clash_findings(conn, before_entries, composites)}
    after_findings = {f.dedupe_key(): f for f in run_clash_findings(conn, after_entries, composites)}

    introduced = [f for k, f in after_findings.items() if k not in before_findings]
    resolved = [f for k, f in before_findings.items() if k not in after_findings]

    originating_finding_ids = [
        r["finding_id"] for r in conn.execute(
            "SELECT DISTINCT pcf.finding_id FROM proposed_change_finding pcf "
            "JOIN proposed_change pc ON pc.id = pcf.proposed_change_id WHERE pc.change_set_id = ?",
            (change_set_id,),
        )
    ]
    unresolved_originating = []
    for finding_id in originating_finding_ids:
        row = conn.execute("SELECT dedupe_key, status FROM finding WHERE id = ?", (finding_id,)).fetchone()
        if row is None:
            continue
        if row["status"] == "RESOLVED" or row["dedupe_key"] not in after_findings:
            continue
        unresolved_originating.append(finding_id)

    is_valid = len(introduced) == 0 and len(unresolved_originating) == 0

    result = {
        "valid": is_valid,
        "reason": None if is_valid else _invalid_reason(introduced, unresolved_originating),
        "introduced_findings": [_finding_summary(f) for f in introduced],
        "resolved_findings": [_finding_summary(f) for f in resolved],
        "unresolved_originating_findings": unresolved_originating,
    }
    _store_validation(conn, change_set_id, result)
    return result


def _invalid_reason(introduced: list[Finding], unresolved_originating: list[int]) -> str:
    parts = []
    if introduced:
        parts.append(f"introduces {len(introduced)} new finding(s)")
    if unresolved_originating:
        parts.append(f"leaves {len(unresolved_originating)} originating finding(s) unresolved")
    return "; ".join(parts)


def _finding_summary(f: Finding) -> dict:
    return {"rule_id": f.rule_id, "severity": f.severity, "title": f.title}


def _store_validation(conn: sqlite3.Connection, change_set_id: int, result: dict) -> None:
    now = dt.datetime.now(dt.UTC).isoformat()
    conn.execute(
        "UPDATE change_set SET validation_status = ?, validation_result_json = ?, validated_at = ? WHERE id = ?",
        ("VALID" if result["valid"] else "INVALID", json.dumps(result), now, change_set_id),
    )
    conn.commit()


def approve_change_set(conn: sqlite3.Connection, change_set_id: int, reviewed_by: str) -> None:
    row = _require_draft(conn, change_set_id)
    if row["validation_status"] != "VALID":
        raise ChangeSetError(
            f"Change set {change_set_id} is {row['validation_status']}, not VALID - validate it first"
        )
    conn.execute(
        "UPDATE change_set SET approval_status = 'APPROVED', reviewed_at = ?, reviewed_by = ? WHERE id = ?",
        (dt.datetime.now(dt.UTC).isoformat(), reviewed_by, change_set_id),
    )
    conn.commit()


def reject_change_set(conn: sqlite3.Connection, change_set_id: int, reviewed_by: str) -> None:
    row = conn.execute("SELECT id FROM change_set WHERE id = ?", (change_set_id,)).fetchone()
    if row is None:
        raise ChangeSetError(f"No change set {change_set_id}")
    conn.execute(
        "UPDATE change_set SET approval_status = 'REJECTED', reviewed_at = ?, reviewed_by = ? WHERE id = ?",
        (dt.datetime.now(dt.UTC).isoformat(), reviewed_by, change_set_id),
    )
    conn.commit()

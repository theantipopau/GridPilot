"""Aggregate real numbers about the current timetable for the Dashboard
page - every figure here is a live query against the working database,
never a fabricated or placeholder metric. Deliberately excludes anything
GridPilot doesn't actually compute (no "compliance score", no solver
status, no scenario comparison) - see docs/project-status.md's
2026-08-06 entry for why those were left out of the dashboard mockup this
was built from."""

import sqlite3
from collections import defaultdict

from fastapi import APIRouter, Depends

from app.api.deps import get_db

router = APIRouter()


@router.get("/dashboard")
def get_dashboard(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    counts = {
        "teachers": conn.execute("SELECT COUNT(*) FROM teacher").fetchone()[0],
        "rooms": conn.execute("SELECT COUNT(*) FROM room").fetchone()[0],
        "roll_classes": conn.execute("SELECT COUNT(*) FROM roll_class").fetchone()[0],
        "students": conn.execute("SELECT COUNT(*) FROM student").fetchone()[0],
        "class_names": conn.execute("SELECT COUNT(*) FROM class_name").fetchone()[0],
        "lessons": conn.execute(
            "SELECT COUNT(*) FROM timetable_entry WHERE entry_type = 'LESSON'"
        ).fetchone()[0],
        "days": conn.execute("SELECT COUNT(*) FROM day").fetchone()[0],
        "periods_per_day": conn.execute(
            "SELECT COUNT(DISTINCT period_no) FROM period WHERE entry_kind = 'LESSON_SLOT'"
        ).fetchone()[0],
    }

    findings_by_severity = {"critical": 0, "warning": 0, "info": 0}
    for r in conn.execute("SELECT severity, COUNT(*) c FROM finding WHERE status = 'OPEN' GROUP BY severity"):
        findings_by_severity[r["severity"]] = r["c"]

    composites_pending = conn.execute(
        "SELECT COUNT(*) FROM composite_group WHERE review_status = 'PENDING'"
    ).fetchone()[0]

    change_sets_draft = conn.execute(
        "SELECT COUNT(*) FROM change_set WHERE approval_status = 'DRAFT'"
    ).fetchone()[0]

    # Average room utilisation - same distinct-(day,period)-slot method as
    # app.analysis.load_rules.room_underutilization, just aggregated across
    # every room instead of filtered to the underutilised ones.
    total_lesson_slots = conn.execute(
        "SELECT COUNT(*) FROM period WHERE entry_kind = 'LESSON_SLOT'"
    ).fetchone()[0]
    room_ids = [r["id"] for r in conn.execute("SELECT id FROM room")]
    utilisation_pct = None
    if total_lesson_slots and room_ids:
        used_slots_by_room: dict[int, set] = defaultdict(set)
        for e in conn.execute(
            "SELECT room_id, day_id, period_id FROM timetable_entry "
            "WHERE entry_type = 'LESSON' AND room_id IS NOT NULL"
        ):
            used_slots_by_room[e["room_id"]].add((e["day_id"], e["period_id"]))
        total_used = sum(len(v) for v in used_slots_by_room.values())
        utilisation_pct = round(100 * total_used / (len(room_ids) * total_lesson_slots), 1)

    last_run = conn.execute(
        "SELECT occurred_at FROM audit_event WHERE event_type = 'rules_run_completed' ORDER BY id DESC LIMIT 1"
    ).fetchone()

    return {
        "counts": counts,
        "findings_by_severity": findings_by_severity,
        "composites_pending": composites_pending,
        "change_sets_draft": change_sets_draft,
        "room_utilisation_pct": utilisation_pct,
        "last_rules_run_at": last_run["occurred_at"] if last_run else None,
    }

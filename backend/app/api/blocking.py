"""Read-only view of the blocking pattern / option lines (Phase C,
docs/full-timetabler-plan.md) - the board a timetabler currently has to
infer from a spreadsheet. Built entirely from blocking_line/
blocking_line_class_group, parsed from the .tfx's MRCGs in Phase A.

Analytics layer added docs/roadmap-v2.md 3.4.1: which lines are
structurally responsible for the most open findings, and each course's
real enrolment. Deliberately NOT a judgement ("under-subscribed") - a
real-data check while building this found a roll class with zero
enrolment against several of its own blocking-line classes despite
having plenty of enrolment elsewhere, which reads as a routing/
composite-coverage question worth a human's attention, not something
confidently classifiable as "this offering is under-subscribed." The
enrolment count is shown as fact; only open_finding_count is an
aggregate judgement, and it's built entirely from findings the rules
engine already trusts - nothing new is inferred here."""

import json
import sqlite3
from collections import defaultdict

from fastapi import APIRouter, Depends

from app.api.deps import get_db

router = APIRouter()


def _split_default_code(default_code: str) -> tuple[str, str]:
    """'10A B' -> ('10A', 'B'); '12 A' -> ('12', 'A'). The part before the
    last space is TTS's own internal grouping label - confirmed NOT to be
    simply "year level cohort" (group '12' covers Fratelli/Assembly/Break
    for every roll class from 7A to RTC, not just Year 12 - checked
    against the real export), so shown verbatim rather than reinterpreted.
    The trailing token is the line letter."""
    group, _, line = default_code.rpartition(" ")
    return (group or default_code), (line or "")


def _enrolled_by_class_name_id(conn: sqlite3.Connection) -> dict[int, int]:
    return {
        r["class_name_id"]: r["n"]
        for r in conn.execute("SELECT class_name_id, COUNT(DISTINCT student_id) AS n FROM enrolment GROUP BY class_name_id")
    }


def _open_finding_count_by_line(
    conn: sqlite3.Connection, class_groups_by_line: dict[int, list[dict]]
) -> dict[int, int]:
    """A finding counts against every line it touches (a teacher double-
    booking can implicate two different lines at once) - "structurally
    responsible for," not a mutually-exclusive attribution."""
    codes_by_line: dict[int, set[tuple[str, str]]] = defaultdict(set)
    for line_id, cgs in class_groups_by_line.items():
        for cg in cgs:
            for c in cg["courses"]:
                if c["class_name_code"]:
                    codes_by_line[line_id].add(("class", c["class_name_code"]))
                if c["teacher_code"]:
                    codes_by_line[line_id].add(("teacher", c["teacher_code"]))
                if c["room_code"]:
                    codes_by_line[line_id].add(("room", c["room_code"]))

    counts: dict[int, int] = defaultdict(int)
    findings = conn.execute("SELECT entity_refs_json FROM finding WHERE status = 'OPEN'").fetchall()
    for row in findings:
        finding_keys = {(r["type"], r["code"]) for r in json.loads(row["entity_refs_json"])}
        for line_id, line_keys in codes_by_line.items():
            if finding_keys & line_keys:
                counts[line_id] += 1
    return counts


@router.get("/blocking-lines")
def list_blocking_lines(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    lines = conn.execute(
        "SELECT id, default_code, code, name FROM blocking_line ORDER BY default_code"
    ).fetchall()

    enrolled_by_class_id = _enrolled_by_class_name_id(conn)

    class_groups_by_line: dict[int, list[dict]] = defaultdict(list)
    cg_rows = conn.execute(
        """
        SELECT blcg.blocking_line_id, cg.id AS class_group_id, rc.code AS roll_class_code,
               cg.periods_per_cycle
        FROM blocking_line_class_group blcg
        JOIN class_group cg ON cg.id = blcg.class_group_id
        JOIN roll_class rc ON rc.id = cg.roll_class_id
        ORDER BY rc.code
        """
    ).fetchall()
    class_group_by_id: dict[int, dict] = {}
    for r in cg_rows:
        cg = {
            "roll_class_code": r["roll_class_code"],
            "periods_per_cycle": r["periods_per_cycle"],
            "courses": [],
        }
        class_group_by_id[r["class_group_id"]] = cg
        class_groups_by_line[r["blocking_line_id"]].append(cg)

    course_rows = conn.execute(
        """
        SELECT cgc.class_group_id, cgc.class_name_id, cn.code AS class_name_code,
               t.code AS teacher_code, rm.code AS room_code
        FROM class_group_course cgc
        LEFT JOIN class_name cn ON cn.id = cgc.class_name_id
        LEFT JOIN teacher t ON t.id = cgc.teacher_id
        LEFT JOIN room rm ON rm.id = cgc.room_id
        """
    ).fetchall()
    for r in course_rows:
        cg = class_group_by_id.get(r["class_group_id"])
        if cg is None:
            continue  # class group not on any blocking line - not relevant to this view
        cg["courses"].append({
            "class_name_code": r["class_name_code"],
            "teacher_code": r["teacher_code"],
            "room_code": r["room_code"],
            "enrolled_count": enrolled_by_class_id.get(r["class_name_id"]) if r["class_name_id"] else None,
        })

    finding_counts = _open_finding_count_by_line(conn, class_groups_by_line)

    groups: dict[str, list[dict]] = defaultdict(list)
    for line in lines:
        group_label, line_label = _split_default_code(line["default_code"])
        groups[group_label].append({
            "id": line["id"],
            "default_code": line["default_code"],
            "line": line_label,
            "code": line["code"],
            "name": line["name"],
            "class_groups": class_groups_by_line.get(line["id"], []),
            "open_finding_count": finding_counts.get(line["id"], 0),
        })

    return {
        "groups": [
            {"group": group_label, "lines": sorted(group_lines, key=lambda l: l["line"])}
            for group_label, group_lines in sorted(groups.items())
        ]
    }

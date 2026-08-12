"""Read-only view of the blocking pattern / option lines (Phase C,
docs/full-timetabler-plan.md) - the board a timetabler currently has to
infer from a spreadsheet. Built entirely from blocking_line/
blocking_line_class_group, parsed from the .tfx's MRCGs in Phase A."""

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


@router.get("/blocking-lines")
def list_blocking_lines(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    lines = conn.execute(
        "SELECT id, default_code, code, name FROM blocking_line ORDER BY default_code"
    ).fetchall()

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
        SELECT cgc.class_group_id, cn.code AS class_name_code, t.code AS teacher_code, rm.code AS room_code
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
        })

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
        })

    return {
        "groups": [
            {"group": group_label, "lines": sorted(group_lines, key=lambda l: l["line"])}
            for group_label, group_lines in sorted(groups.items())
        ]
    }

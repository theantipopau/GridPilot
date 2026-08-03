import sqlite3

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db

router = APIRouter()


@router.get("/timetable-entries")
def find_timetable_entries(
    day_code: str | None = None,
    period_code: str | None = None,
    teacher_code: str | None = None,
    room_code: str | None = None,
    class_code: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Lookup helper for building a proposed change: given some of a
    finding's entity/slot codes, find the matching timetable_entry rows to
    target. Read-only, used by the Change Sets UI's 'propose a fix' flow."""
    sql = """
        SELECT te.id AS entry_id,
               d.code AS day_code, p.code AS period_code,
               cn.code AS class_code, rm.code AS room_code, t.code AS teacher_code,
               rc.code AS roll_class_code
        FROM timetable_entry te
        JOIN day d ON d.id = te.day_id
        JOIN period p ON p.id = te.period_id
        JOIN roll_class rc ON rc.id = te.roll_class_id
        LEFT JOIN class_name cn ON cn.id = te.class_name_id
        LEFT JOIN room rm ON rm.id = te.room_id
        LEFT JOIN teacher t ON t.id = te.teacher_id
        WHERE te.entry_type = 'LESSON'
    """
    params: list = []
    if day_code:
        sql += " AND d.code = ?"
        params.append(day_code)
    if period_code:
        sql += " AND p.code = ?"
        params.append(period_code)
    if teacher_code:
        sql += " AND t.code = ?"
        params.append(teacher_code)
    if room_code:
        sql += " AND rm.code = ?"
        params.append(room_code)
    if class_code:
        sql += " AND cn.code = ?"
        params.append(class_code)
    sql += " ORDER BY te.id"

    rows = conn.execute(sql, params).fetchall()
    return {"entries": [dict(r) for r in rows]}

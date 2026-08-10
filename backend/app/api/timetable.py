import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_db

router = APIRouter()

VIEW_FILTER_COLUMN = {
    "teacher": "t.code",
    "room": "rm.code",
    "roll_class": "rc.code",
}

VIEW_LABEL_QUERY = {
    "teacher": "SELECT first_name || ' ' || last_name FROM teacher WHERE code = ?",
    "room": "SELECT name FROM room WHERE code = ?",
    "roll_class": "SELECT code FROM roll_class WHERE code = ?",
}


TIMETABLE_ENTRY_COLUMNS = """
    te.id AS entry_id,
    d.code AS day_code, d.day_no, d.week_label,
    p.code AS period_code, p.period_no, p.name AS period_name, p.entry_kind,
    te.entry_type,
    cn.code AS class_code, cn.name AS class_name, sub.name AS subject_name,
    rm.code AS room_code, rm.name AS room_name,
    t.code AS teacher_code, t.first_name AS teacher_first_name, t.last_name AS teacher_last_name,
    rc.code AS roll_class_code
"""

TIMETABLE_ENTRY_JOINS = """
    FROM timetable_entry te
    JOIN day d ON d.id = te.day_id
    JOIN period p ON p.id = te.period_id
    JOIN roll_class rc ON rc.id = te.roll_class_id
    LEFT JOIN class_name cn ON cn.id = te.class_name_id
    LEFT JOIN subject sub ON sub.id = cn.subject_id
    LEFT JOIN room rm ON rm.id = te.room_id
    LEFT JOIN teacher t ON t.id = te.teacher_id
"""


@router.get("/timetable/all")
def get_full_timetable(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """Every lesson in the school at once, unfiltered - the master grid
    (docs/master-timetable.md). Distinct from GET /timetable, which needs a
    single teacher/room/roll_class to filter to. Reference data (rooms,
    teachers, roll_classes) already loaded client-side supplies the row
    list; this just supplies every entry to group by whichever axis the
    user picks."""
    rows = conn.execute(
        f"SELECT {TIMETABLE_ENTRY_COLUMNS} {TIMETABLE_ENTRY_JOINS} ORDER BY d.day_no, p.period_no"
    ).fetchall()
    return {"entries": [dict(r) for r in rows]}


@router.get("/timetable")
def get_timetable(
    view: str = Query(..., pattern="^(teacher|room|roll_class)$"),
    code: str = Query(...),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    label_row = conn.execute(VIEW_LABEL_QUERY[view], (code,)).fetchone()
    if label_row is None:
        raise HTTPException(status_code=404, detail=f"No {view} with code {code!r}")

    filter_column = VIEW_FILTER_COLUMN[view]
    rows = conn.execute(
        f"SELECT {TIMETABLE_ENTRY_COLUMNS} {TIMETABLE_ENTRY_JOINS} WHERE {filter_column} = ? "
        f"ORDER BY d.day_no, p.period_no",
        (code,),
    ).fetchall()

    return {
        "view": view,
        "code": code,
        "label": label_row[0],
        "entries": [dict(r) for r in rows],
    }

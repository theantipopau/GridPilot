import sqlite3

from fastapi import APIRouter, Depends

from app.api.deps import get_db

router = APIRouter()


@router.get("/reference")
def get_reference(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    days = [dict(r) for r in conn.execute(
        "SELECT code, day_no, week_label FROM day ORDER BY day_no"
    )]
    periods = [dict(r) for r in conn.execute(
        "SELECT p.code, p.name, d.code AS day_code, p.period_no, p.start_time, p.finish_time, p.entry_kind "
        "FROM period p JOIN day d ON d.id = p.day_id ORDER BY d.day_no, p.period_no"
    )]
    rooms = [dict(r) for r in conn.execute(
        "SELECT code, name, seats, room_type FROM room ORDER BY code"
    )]
    teachers = [dict(r) for r in conn.execute(
        "SELECT code, first_name, last_name, staff_category FROM teacher ORDER BY last_name, first_name"
    )]
    roll_classes = [dict(r) for r in conn.execute(
        "SELECT rc.code, yl.code AS year_level_code, rc.is_support_roll_class FROM roll_class rc "
        "LEFT JOIN year_level yl ON yl.id = rc.year_level_id ORDER BY yl.code IS NULL, yl.code, rc.code"
    )]
    year_levels = [dict(r) for r in conn.execute(
        "SELECT code FROM year_level ORDER BY code"
    )]
    return {
        "days": days,
        "periods": periods,
        "rooms": rooms,
        "teachers": teachers,
        "roll_classes": roll_classes,
        "year_levels": year_levels,
    }

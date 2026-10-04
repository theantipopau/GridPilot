"""Read-only per-teacher load breakdown - see app/analysis/teacher_loads.py."""

import sqlite3

from fastapi import APIRouter, Depends

from app.analysis.teacher_loads import compute_teacher_loads
from app.api.deps import get_db

router = APIRouter()


@router.get("/teacher-loads")
def teacher_loads(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return compute_teacher_loads(conn)

"""Central path configuration. Source exports are read-only; everything the
app writes goes under DATA_DIR / OUTPUT_DIR, never back into SOURCE_DIR."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SOURCE_DIR = Path(os.environ.get("TT_SOURCE_DIR", PROJECT_ROOT / "Timetabler Export"))
DATA_DIR = Path(os.environ.get("TT_DATA_DIR", PROJECT_ROOT / "data"))
OUTPUT_DIR = Path(os.environ.get("TT_OUTPUT_DIR", PROJECT_ROOT / "output"))

DB_PATH = DATA_DIR / "sophia_tt.sqlite3"

TFX_PATH = SOURCE_DIR / "TT files" / "TT 2026 Term Three Week 4.tfx"

CSV_DIR = SOURCE_DIR
ROOM_DETAILS_CSV = SOURCE_DIR / "Room Details.csv"
PERIOD_DETAILS_CSV = SOURCE_DIR / "Period Details.csv"
TEACHER_DETAILS_CSV = SOURCE_DIR / "Teacher Details.csv"
STUDENT_DETAILS_CSV = SOURCE_DIR / "Student Details.csv"
ROLL_CLASS_DETAILS_CSV = SOURCE_DIR / "Roll Class Details.csv"
MASTER_TIMETABLE_CYCLE_CSV = SOURCE_DIR / "Master Timetable Cycle.csv"

EMINERVA_SCOURSE_PATH = SOURCE_DIR / "eMinervaSCourse.txt"
EMINERVA_TTABLE_PATH = SOURCE_DIR / "eMinervaTTable.txt"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

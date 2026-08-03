"""Builds a small, fully synthetic in-memory database for rules-engine
tests. No real school data anywhere here or in git - see
PROJECT_ROADMAP.md's privacy correction ('synthetic fixtures only in
Git'). Reference data is a minimal fixed set; each test inserts its own
timetable_entry/enrolment rows on top."""

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parents[1] / "app" / "db" / "schema.sql"


def build_synthetic_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    # Cycle: 2 synthetic days, 2 periods each (one LESSON_SLOT, one BREAK).
    conn.execute("INSERT INTO day (id, code, day_no, week_label) VALUES (1, 'Day 1 A', 1, 'A')")
    conn.execute("INSERT INTO day (id, code, day_no, week_label) VALUES (2, 'Day 2 A', 2, 'A')")
    conn.execute(
        "INSERT INTO period (id, code, name, day_id, period_no, load_minutes, entry_kind) "
        "VALUES (1, 'P1', 'Period 1', 1, 1, 60, 'LESSON_SLOT')"
    )
    conn.execute(
        "INSERT INTO period (id, code, name, day_id, period_no, load_minutes, entry_kind) "
        "VALUES (2, 'FB', 'Break', 1, 2, 0, 'BREAK')"
    )
    conn.execute(
        "INSERT INTO period (id, code, name, day_id, period_no, load_minutes, entry_kind) "
        "VALUES (3, 'P1', 'Period 1', 2, 1, 60, 'LESSON_SLOT')"
    )

    conn.execute("INSERT INTO room (id, code, name) VALUES (1, 'R1', 'Room 1')")
    conn.execute("INSERT INTO room (id, code, name) VALUES (2, 'R2', 'Room 2')")

    conn.execute("INSERT INTO teacher (id, code, first_name, last_name) VALUES (1, 'T1', 'Test', 'One')")
    conn.execute("INSERT INTO teacher (id, code, first_name, last_name) VALUES (2, 'T2', 'Test', 'Two')")

    conn.execute("INSERT INTO year_level (id, code) VALUES (1, '07')")
    conn.execute("INSERT INTO roll_class (id, code, year_level_id) VALUES (1, '7A', 1)")
    conn.execute("INSERT INTO roll_class (id, code, year_level_id) VALUES (2, '7B', 1)")

    conn.execute("INSERT INTO subject (id, source_code, name) VALUES (1, 'SUBA', 'Subject A')")
    conn.execute("INSERT INTO subject (id, source_code, name) VALUES (2, 'SUBB', 'Subject B')")
    conn.execute("INSERT INTO class_name (id, code, name, subject_id) VALUES (1, 'CLASSA', 'Class A', 1)")
    conn.execute("INSERT INTO class_name (id, code, name, subject_id) VALUES (2, 'CLASSB', 'Class B', 2)")

    conn.execute("INSERT INTO student (id, code, first_name, last_name, roll_class_id) VALUES (1, '100001', 'Test', 'Student', 1)")

    conn.commit()
    return conn


def build_richer_synthetic_db() -> sqlite3.Connection:
    """Wider fixture for tests that need a real search space (the
    suggestion engine) - 3 days x 2 lesson periods, 3 rooms (one with a
    tiny confirmed capacity, to test capacity rejection)."""
    conn = build_synthetic_db()

    conn.execute("INSERT INTO day (id, code, day_no, week_label) VALUES (3, 'Day 3 A', 3, 'A')")
    conn.execute(
        "INSERT INTO period (id, code, name, day_id, period_no, load_minutes, entry_kind) "
        "VALUES (4, 'P2', 'Period 2', 1, 3, 60, 'LESSON_SLOT')"
    )
    conn.execute(
        "INSERT INTO period (id, code, name, day_id, period_no, load_minutes, entry_kind) "
        "VALUES (5, 'P2', 'Period 2', 2, 3, 60, 'LESSON_SLOT')"
    )
    conn.execute(
        "INSERT INTO period (id, code, name, day_id, period_no, load_minutes, entry_kind) "
        "VALUES (6, 'P1', 'Period 1', 3, 1, 60, 'LESSON_SLOT')"
    )
    conn.execute("INSERT INTO room (id, code, name, seats) VALUES (3, 'R3', 'Room 3', 1)")
    conn.commit()
    return conn


def add_lesson(conn: sqlite3.Connection, *, day_id: int, period_id: int, roll_class_id: int,
                class_name_id: int, teacher_id: int | None, room_id: int | None) -> None:
    conn.execute(
        "INSERT INTO timetable_entry (source_ref, day_id, period_id, roll_class_id, class_name_id, "
        "room_id, teacher_id, entry_type) VALUES ('test', ?, ?, ?, ?, ?, ?, 'LESSON')",
        (day_id, period_id, roll_class_id, class_name_id, room_id, teacher_id),
    )
    conn.commit()


def add_break(conn: sqlite3.Connection, *, day_id: int, period_id: int, roll_class_id: int) -> None:
    conn.execute(
        "INSERT INTO timetable_entry (source_ref, day_id, period_id, roll_class_id, entry_type) "
        "VALUES ('test', ?, ?, ?, 'BREAK')",
        (day_id, period_id, roll_class_id),
    )
    conn.commit()


def add_enrolment(conn: sqlite3.Connection, *, student_id: int, class_name_id: int) -> None:
    conn.execute(
        "INSERT INTO enrolment (student_id, class_name_id, source) VALUES (?, ?, 'test')",
        (student_id, class_name_id),
    )
    conn.commit()

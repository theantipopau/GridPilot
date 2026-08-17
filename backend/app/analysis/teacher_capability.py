"""Detects which (teacher, subject) pairs are currently observed in the
timetable - the bootstrap-from-timetable input for teacher_capability
(docs/roadmap-v2.md 2.2, docs/staff-capability-model.md). Unlike room-type
detection (a *ratio* signal - does a class mostly sit in one room type),
this is a plain observation: the teacher is currently teaching this
subject, full stop. No threshold to tune - either the pairing exists in
the resolved timetable or it doesn't.

Real-data check before building this: 213 distinct (teacher, subject)
pairs across 40 teachers with LESSON entries (of 74 total - the rest
carry no lesson-bearing timetable_entry rows at all, e.g. non-teaching
duties only), median 5 subjects/teacher, max 11 - a plausible, non-
degenerate spread for a real secondary timetable, not a data artefact."""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class TeacherSubjectPairing:
    teacher_code: str
    subject_code: str
    faculty_code: str | None
    lesson_count: int


def observed_teacher_subject_pairings(conn: sqlite3.Connection) -> list[TeacherSubjectPairing]:
    rows = conn.execute(
        """
        SELECT t.code AS teacher_code, s.source_code AS subject_code, f.code AS faculty_code,
               COUNT(*) AS lesson_count
        FROM timetable_entry te
        JOIN teacher t ON t.id = te.teacher_id
        JOIN class_name cn ON cn.id = te.class_name_id
        JOIN subject s ON s.id = cn.subject_id
        LEFT JOIN faculty f ON f.id = s.faculty_id
        WHERE te.entry_type = 'LESSON'
        GROUP BY t.id, s.id
        ORDER BY t.code, s.source_code
        """
    ).fetchall()
    return [
        TeacherSubjectPairing(r["teacher_code"], r["subject_code"], r["faculty_code"], r["lesson_count"])
        for r in rows
    ]

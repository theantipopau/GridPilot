"""Parses eMinervaSCourse.txt - the deduplicated student<->class enrolment
list eMinerva expects/produces - and reconciles it against the enrolment
rows already derived from .tfx Students[].StudentLessons[]. See
docs/data-formats.md #4."""

import csv
import json
import sqlite3
from pathlib import Path

from app.ingest.errors import IngestError


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _log(conn: sqlite3.Connection, run_id: int, check_name: str, severity: str, description: str, detail=None) -> None:
    conn.execute(
        "INSERT INTO ingest_discrepancy (ingest_run_id, check_name, severity, description, detail_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, check_name, severity, description, json.dumps(detail) if detail else None),
    )


def ingest_eminerva_scourse(conn: sqlite3.Connection, run_id: int, path: Path) -> None:
    rows = _read_csv(path)

    student_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM student")}
    class_name_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM class_name")}

    eminerva_pairs: set[tuple[int, int]] = set()

    for row in rows:
        student_code = row["StudentCode"]
        class_code = row["ClassName"]
        student_id = student_id_by_code.get(student_code)
        if student_id is None:
            raise IngestError(f"eMinervaSCourse.txt references StudentCode {student_code!r} not found in .tfx Students[]")
        class_name_id = class_name_id_by_code.get(class_code)
        if class_name_id is None:
            raise IngestError(f"eMinervaSCourse.txt references ClassName {class_code!r} not found in .tfx ClassNames[]")

        eminerva_pairs.add((student_id, class_name_id))

        existing = conn.execute(
            "SELECT id, source FROM enrolment WHERE student_id = ? AND class_name_id = ?",
            (student_id, class_name_id),
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO enrolment (student_id, class_name_id, source) VALUES (?, ?, ?)",
                (student_id, class_name_id, "eminerva"),
            )
            _log(conn, run_id, "enrolment_only_in_eminerva", "warning",
                 "Enrolment present in eMinervaSCourse.txt but not derivable from .tfx StudentLessons[]",
                 {"class_code": class_code})
        elif "eminerva" not in existing["source"].split(","):
            conn.execute(
                "UPDATE enrolment SET source = ? WHERE id = ?",
                (existing["source"] + ",eminerva", existing["id"]),
            )

    tfx_only = conn.execute(
        "SELECT student_id, class_name_id FROM enrolment WHERE source = 'tfx'"
    ).fetchall()
    if tfx_only:
        _log(conn, run_id, "enrolment_only_in_tfx", "warning",
             f"{len(tfx_only)} enrolment(s) derived from .tfx StudentLessons[] have no matching row in "
             f"eMinervaSCourse.txt", {"count": len(tfx_only)})

    conn.commit()

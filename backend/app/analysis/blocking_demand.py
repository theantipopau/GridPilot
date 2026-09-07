"""Blocking Phase 1 - structural demand analysis from the .sfx subject-
selection export, docs/roadmap-v3.md §4.1/§12.4. No new data, no solver:
everything here is computed from sfx_subject/sfx_option/sfx_class/sfx_line
(what a student *could* pick) cross-referenced with the resolved
timetable's real enrolment (what actually happened).

Restricted throughout to sfx_class rows whose class_code resolves to a
real LESSON entry in the current timetable (the same LESSON-only
convention as app/analysis/contact_time.py). Checked against real data,
unfiltered this pulls in Fratelli/Assembly/Registration house-pastoral
groups - house codes like 'IGN5'/'SOL5' are reused as the class_code
across many different roll classes with wildly different max_class_size
values, which made 199 of 445 matched classes read as "over capacity"
purely from that duplication, and every one of them resolved to
entry_type REGISTRATION, not a taught elective. Filtered to LESSON only,
the false "over capacity" signal disappears entirely (0 of 181) and
class_code becomes unique, which is itself worth recording: this school's
elective offerings are not currently over-subscribed anywhere against
their own stated caps."""

import sqlite3
from collections import defaultdict


def _lesson_class_codes(conn: sqlite3.Connection) -> set[str]:
    return {
        r["code"]
        for r in conn.execute(
            """
            SELECT DISTINCT cn.code
            FROM class_name cn
            JOIN timetable_entry te ON te.class_name_id = cn.id
            WHERE te.entry_type = 'LESSON'
            """
        )
    }


def _enrolled_by_class_name(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        r["code"]: r["n"]
        for r in conn.execute(
            """
            SELECT cn.code, COUNT(DISTINCT e.student_id) AS n
            FROM class_name cn LEFT JOIN enrolment e ON e.class_name_id = cn.id
            GROUP BY cn.id
            """
        )
    }


def compute_blocking_demand(conn: sqlite3.Connection) -> dict:
    lesson_codes = _lesson_class_codes(conn)
    enrolled_by_code = _enrolled_by_class_name(conn)

    classes: dict[str, dict] = {}
    line_meta: dict[int, dict] = {}
    for r in conn.execute(
        """
        SELECT sc.class_code, sc.subject_code, sc.roll_class_code, sc.max_class_size,
               sc.sfx_line_id, sl.code AS line_code, sl.name AS line_name
        FROM sfx_class sc
        JOIN sfx_line sl ON sl.id = sc.sfx_line_id
        WHERE sc.class_code IS NOT NULL
        """
    ):
        if r["class_code"] not in lesson_codes:
            continue
        line_meta[r["sfx_line_id"]] = {"code": r["line_code"], "name": r["line_name"]}
        classes[r["class_code"]] = {
            "class_code": r["class_code"],
            "subject_code": r["subject_code"],
            "roll_class_code": r["roll_class_code"],
            "max_class_size": r["max_class_size"],
            "sfx_line_id": r["sfx_line_id"],
            "line_code": r["line_code"],
            "enrolled": enrolled_by_code.get(r["class_code"]),
        }

    # Subject-pair impossibility: a subject confined to exactly one line
    # can never be combined with another subject confined to that same
    # line - a student picks at most one class per line.
    lines_by_subject: dict[str, set[int]] = defaultdict(set)
    for c in classes.values():
        lines_by_subject[c["subject_code"]].add(c["sfx_line_id"])

    singleton_subjects_by_line: dict[int, list[str]] = defaultdict(list)
    for subject, line_ids in lines_by_subject.items():
        if len(line_ids) == 1:
            singleton_subjects_by_line[next(iter(line_ids))].append(subject)

    impossible_subject_pairs = [
        {
            "sfx_line_id": line_id,
            "line_code": line_meta[line_id]["code"],
            "line_name": line_meta[line_id]["name"],
            "subjects": sorted(subjects),
        }
        for line_id, subjects in singleton_subjects_by_line.items()
        if len(subjects) >= 2
    ]
    impossible_subject_pairs.sort(key=lambda g: (-len(g["subjects"]), g["line_code"] or ""))

    # Per-line demand pressure: real enrolment against the school's own
    # stated capacity, across that line's LESSON classes.
    totals_by_line: dict[int, dict] = defaultdict(lambda: {"capacity": 0, "enrolled": 0, "class_count": 0})
    for c in classes.values():
        if c["enrolled"] is None or not c["max_class_size"]:
            continue
        t = totals_by_line[c["sfx_line_id"]]
        t["capacity"] += c["max_class_size"]
        t["enrolled"] += c["enrolled"]
        t["class_count"] += 1

    lines = [
        {
            "sfx_line_id": line_id,
            "line_code": line_meta[line_id]["code"],
            "line_name": line_meta[line_id]["name"],
            "class_count": t["class_count"],
            "total_capacity": t["capacity"],
            "total_enrolled": t["enrolled"],
            "pressure": round(t["enrolled"] / t["capacity"], 3) if t["capacity"] else None,
        }
        for line_id, t in totals_by_line.items()
    ]
    lines.sort(key=lambda l: (l["pressure"] is None, -(l["pressure"] or 0)))

    # Under-subscribed classes: real enrolment vs the school's own stated
    # cap, shown as fact (see module docstring - "over-subscribed" is not
    # asserted anywhere here, because checked against real data there
    # currently isn't any).
    under_subscribed_classes = [
        {
            "class_code": c["class_code"],
            "subject_code": c["subject_code"],
            "roll_class_code": c["roll_class_code"],
            "line_code": c["line_code"],
            "enrolled": c["enrolled"],
            "max_class_size": c["max_class_size"],
            "fill_ratio": round(c["enrolled"] / c["max_class_size"], 3),
        }
        for c in classes.values()
        if c["enrolled"] is not None and c["max_class_size"] and c["enrolled"] < c["max_class_size"] * 0.5
    ]
    under_subscribed_classes.sort(key=lambda c: (c["fill_ratio"], -c["max_class_size"]))

    return {
        "impossible_subject_pairs": impossible_subject_pairs,
        "lines": lines,
        "under_subscribed_classes": under_subscribed_classes,
    }

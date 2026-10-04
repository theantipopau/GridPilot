"""Per-teacher load breakdown for the Loads view - the same numbers
app.analysis.load_rules.teacher_over_contracted_load judges, laid out so a
timetabler can see the whole staff at once instead of reading findings one
at a time.

Every figure here is a fact about the current timetable, not a verdict:
scheduled minutes are distinct (teacher, period) slots - a composite
lesson counts once, however many class codes share it - using the same
contact-entry definition the load rule uses (LESSON only, until a school
confirms a wider one: app/analysis/contact_time.py). There is deliberately
no "under-loaded" or "balanced" label - that would be an invented policy
threshold (docs/roadmap-v3.md section 8). What is factual, and is surfaced,
is the contracted figure, minutes scheduled against it, minutes remaining
(negative when over), and how the load is spread across the cycle."""

import sqlite3
from collections import defaultdict

from app.analysis.contact_time import resolve_contact_entry_types


def compute_teacher_loads(conn: sqlite3.Connection) -> dict:
    contact_entry_types = resolve_contact_entry_types(conn)
    placeholders = ",".join("?" for _ in contact_entry_types)

    days = conn.execute("SELECT id, code, day_no FROM day ORDER BY day_no").fetchall()

    # (teacher_id, period_id) is the unit of load: a composite lesson is
    # several timetable_entry rows for one slot, and must count once.
    slots: dict[int, dict[int, dict]] = defaultdict(dict)
    for r in conn.execute(
        f"""
        SELECT te.teacher_id, te.period_id, te.day_id, p.load_minutes
        FROM timetable_entry te
        JOIN period p ON p.id = te.period_id
        WHERE te.entry_type IN ({placeholders}) AND te.teacher_id IS NOT NULL
        """,
        contact_entry_types,
    ):
        slots[r["teacher_id"]][r["period_id"]] = {"day_id": r["day_id"], "minutes": r["load_minutes"]}

    classes_by_teacher: dict[int, set[int]] = defaultdict(set)
    subjects_by_teacher: dict[int, set[int]] = defaultdict(set)
    year_levels_by_teacher: dict[int, set[str]] = defaultdict(set)
    for r in conn.execute(
        """
        SELECT te.teacher_id, te.class_name_id, cn.subject_id, yl.code AS year_level_code
        FROM timetable_entry te
        LEFT JOIN class_name cn ON cn.id = te.class_name_id
        LEFT JOIN roll_class rc ON rc.id = te.roll_class_id
        LEFT JOIN year_level yl ON yl.id = rc.year_level_id
        WHERE te.entry_type = 'LESSON' AND te.teacher_id IS NOT NULL
        """
    ):
        if r["class_name_id"] is not None:
            classes_by_teacher[r["teacher_id"]].add(r["class_name_id"])
        if r["subject_id"] is not None:
            subjects_by_teacher[r["teacher_id"]].add(r["subject_id"])
        if r["year_level_code"]:
            year_levels_by_teacher[r["teacher_id"]].add(r["year_level_code"])

    faculties_by_teacher: dict[int, list[str]] = defaultdict(list)
    for r in conn.execute(
        "SELECT tf.teacher_id, f.code FROM teacher_faculty tf JOIN faculty f ON f.id = tf.faculty_id ORDER BY f.code"
    ):
        faculties_by_teacher[r["teacher_id"]].append(r["code"])

    profile_by_code = {
        r["teacher_code"]: r["fte"] for r in conn.execute("SELECT teacher_code, fte FROM teacher_profile")
    }
    release_by_code = {
        r["teacher_code"]: r["release_minutes_per_cycle"]
        for r in conn.execute(
            "SELECT tra.teacher_code, sr.release_minutes_per_cycle FROM teacher_role_assignment tra "
            "JOIN staff_role sr ON sr.id = tra.staff_role_id"
        )
    }

    teachers = []
    for t in conn.execute(
        "SELECT id, code, first_name, last_name, staff_category, contracted_load_minutes "
        "FROM teacher ORDER BY last_name, first_name"
    ):
        teacher_slots = slots.get(t["id"], {})
        scheduled = sum(s["minutes"] for s in teacher_slots.values())
        contracted = t["contracted_load_minutes"]

        minutes_by_day: dict[int, float] = defaultdict(float)
        periods_by_day: dict[int, int] = defaultdict(int)
        for s in teacher_slots.values():
            minutes_by_day[s["day_id"]] += s["minutes"]
            periods_by_day[s["day_id"]] += 1

        teachers.append({
            "code": t["code"],
            "first_name": t["first_name"],
            "last_name": t["last_name"],
            "staff_category": t["staff_category"],
            "faculty_codes": faculties_by_teacher.get(t["id"], []),
            "contracted_minutes": contracted,
            "scheduled_minutes": scheduled,
            "remaining_minutes": (contracted - scheduled) if contracted is not None else None,
            "percent_of_contract": round(scheduled / contracted * 100, 1) if contracted else None,
            "teaching_periods": len(teacher_slots),
            "class_count": len(classes_by_teacher.get(t["id"], ())),
            "subject_count": len(subjects_by_teacher.get(t["id"], ())),
            "year_levels": sorted(year_levels_by_teacher.get(t["id"], ())),
            "fte": profile_by_code.get(t["code"]),
            "release_minutes_per_cycle": release_by_code.get(t["code"]),
            "by_day": [
                {
                    "day_code": d["code"],
                    "minutes": minutes_by_day.get(d["id"], 0.0),
                    "periods": periods_by_day.get(d["id"], 0),
                }
                for d in days
            ],
        })

    return {"contact_entry_types": list(contact_entry_types), "days": [d["code"] for d in days], "teachers": teachers}

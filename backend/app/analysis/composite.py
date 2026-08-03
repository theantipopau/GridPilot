"""Detects composite classes - two or more official class codes taught as
one physical lesson (same teacher, same room, same periods) - from the
resolved timetable. Nothing in the Timetabling Solutions export marks
this explicitly; it's inferred from repeated co-occurrence. See
docs/data-model.md 'Composite classes' and docs/data-formats.md #5.9.

This is a detection/reporting pass for human review, not yet wired into
the rules engine - see that section for why the result needs confirming
before it's trusted to suppress clash findings."""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class CompositeGroup:
    teacher_code: str
    room_code: str
    class_codes: tuple[str, ...]
    slots: list[tuple[str, str]] = field(default_factory=list)  # (day_code, period_code)

    @property
    def slot_count(self) -> int:
        return len(self.slots)


def detect_composite_groups(conn: sqlite3.Connection, min_slots: int = 2) -> list[CompositeGroup]:
    """A composite group is a (teacher, room) pair where more than one
    distinct class code is scheduled in the exact same slot, and that
    same combination of class codes recurs across at least `min_slots`
    slots in the cycle - repetition is what distinguishes an intentional
    composite from a one-off double-booking (a genuine clash wouldn't
    consistently repeat identically across the whole cycle)."""
    rows = conn.execute(
        """
        SELECT t.code AS teacher_code, rm.code AS room_code,
               d.code AS day_code, p.code AS period_code,
               cn.code AS class_code
        FROM timetable_entry te
        JOIN teacher t ON t.id = te.teacher_id
        JOIN room rm ON rm.id = te.room_id
        JOIN day d ON d.id = te.day_id
        JOIN period p ON p.id = te.period_id
        JOIN class_name cn ON cn.id = te.class_name_id
        WHERE te.entry_type = 'LESSON'
        ORDER BY t.code, rm.code, d.day_no, p.period_no
        """
    ).fetchall()

    # (teacher, room, day, period) -> set of class codes seen in that exact slot
    slot_classes: dict[tuple, set[str]] = defaultdict(set)
    for r in rows:
        key = (r["teacher_code"], r["room_code"], r["day_code"], r["period_code"])
        slot_classes[key].add(r["class_code"])

    # (teacher, room, class-code-combo) -> list of slots where that combo occurred
    combo_slots: dict[tuple, list[tuple[str, str]]] = defaultdict(list)
    for (teacher_code, room_code, day_code, period_code), classes in slot_classes.items():
        if len(classes) < 2:
            continue
        combo = (teacher_code, room_code, tuple(sorted(classes)))
        combo_slots[combo].append((day_code, period_code))

    groups = []
    for (teacher_code, room_code, class_codes), slots in combo_slots.items():
        if len(slots) >= min_slots:
            groups.append(CompositeGroup(teacher_code, room_code, class_codes, sorted(slots)))

    return sorted(groups, key=lambda g: (-g.slot_count, g.class_codes))


if __name__ == "__main__":
    from app.config import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    for g in detect_composite_groups(conn):
        print(f"{g.slot_count:2d} slots  {g.teacher_code:8s} {g.room_code:6s}  {' + '.join(g.class_codes)}")
    conn.close()

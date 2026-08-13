"""Infers which room_type a class actually requires, from how it has
already been scheduled - see docs/solver.md section 4.2. Nothing in the
source export declares a class's required room type explicitly (`room.
room_type` is free text from the export's Notes column, not a controlled
vocabulary - see docs/rules.md's room_feature_mismatch note); this
proposes a candidate for human review, exactly like composite-class
detection (app/analysis/composite.py) - never asserted as fact.

Real-data check before choosing the threshold below: of 231 classes
scheduled in at least one typed room, 180 (78%) already use exactly one
room_type for every lesson, and 220 (95%) use at most two - a strong
enough signal to propose, not strong enough to assert."""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass

MIN_LESSONS = 2  # a "majority" of 1 lesson is noise, not a signal
MIN_RATIO = 0.7  # a documented default heuristic, not a confirmed school policy - same discipline as load_rules.py


@dataclass(frozen=True)
class RoomTypeCandidate:
    class_code: str
    room_type: str
    matching_lesson_count: int
    total_lesson_count: int


def class_room_type_usage(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """class_code -> {room_type: lesson_count}, for every lesson in a
    typed room. The building block both detect_room_type_candidates()
    (below) and room_type_review.py's evidence-refresh logic need - the
    latter has to count matches against a class's *already-reviewed*
    room_type, not just whatever type happens to be the current
    majority (see room_type_review.py's module docstring)."""
    rows = conn.execute(
        """
        SELECT cn.code AS class_code, rm.room_type AS room_type
        FROM timetable_entry te
        JOIN class_name cn ON cn.id = te.class_name_id
        JOIN room rm ON rm.id = te.room_id
        WHERE te.entry_type = 'LESSON' AND rm.room_type IS NOT NULL AND rm.room_type != ''
        """
    ).fetchall()

    counts_by_class: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        counts_by_class[r["class_code"]][r["room_type"]] += 1
    return {code: dict(counts) for code, counts in counts_by_class.items()}


def detect_room_type_candidates(
    conn: sqlite3.Connection, min_ratio: float = MIN_RATIO, min_lessons: int = MIN_LESSONS
) -> list[RoomTypeCandidate]:
    candidates = []
    for class_code, type_counts in class_room_type_usage(conn).items():
        total = sum(type_counts.values())
        if total < min_lessons:
            continue
        majority_type, majority_count = max(type_counts.items(), key=lambda kv: kv[1])
        if majority_count / total < min_ratio:
            continue
        candidates.append(RoomTypeCandidate(class_code, majority_type, majority_count, total))

    return sorted(candidates, key=lambda c: (-(c.matching_lesson_count / c.total_lesson_count), c.class_code))


if __name__ == "__main__":
    from app.config import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    for c in detect_room_type_candidates(conn):
        ratio = c.matching_lesson_count / c.total_lesson_count
        print(f"{ratio:5.0%}  {c.class_code:14s} -> {c.room_type:20s} ({c.matching_lesson_count}/{c.total_lesson_count})")
    conn.close()

"""CapabilityService.resolve() - docs/staff-capability-model.md,
docs/roadmap-v2.md 2.2. Resolves once, here, never duplicated as raw SQL
elsewhere (the addendum's explicit instruction) - the rules engine
(app/analysis/capability_rules.py) and, once B4 lands, the suggestion
engine both call this instead of re-deriving it.

Deliberately narrower than the addendum's full six-step precedence: the
"requirement lock" / "requirement preference" steps need teaching_
requirement / requirement_teacher_preference, which are not built (see
schema.sql's teacher_capability comment - those matter for solver Mode C
construction, not for "is this teacher qualified for this subject" as
asked here). What's implemented is the exact-subject match, the broader
faculty match, and the addendum's explicit fallback: no match at all is
NOT_ELIGIBLE, not REVIEW_REQUIRED - missing data means excluded, not
silently allowed."""

import sqlite3

CapabilityStatus = str  # "ELIGIBLE" | "NOT_ELIGIBLE" | "REVIEW_REQUIRED"


def resolve(conn: sqlite3.Connection, teacher_code: str, subject_code: str, faculty_code: str | None) -> CapabilityStatus:
    """The most specific active teacher_capability row: an exact subject
    match first, then a faculty-level match, else NOT_ELIGIBLE."""
    exact = conn.execute(
        "SELECT capability_status FROM teacher_capability WHERE teacher_code = ? AND subject_code = ? "
        "AND (effective_to IS NULL OR effective_to >= date('now')) ORDER BY effective_from DESC LIMIT 1",
        (teacher_code, subject_code),
    ).fetchone()
    if exact is not None:
        return exact["capability_status"]

    if faculty_code is not None:
        broader = conn.execute(
            "SELECT capability_status FROM teacher_capability WHERE teacher_code = ? AND faculty_code = ? "
            "AND subject_code IS NULL AND (effective_to IS NULL OR effective_to >= date('now')) "
            "ORDER BY effective_from DESC LIMIT 1",
            (teacher_code, faculty_code),
        ).fetchone()
        if broader is not None:
            return broader["capability_status"]

    return "NOT_ELIGIBLE"

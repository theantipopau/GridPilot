"""What counts as EA "contact time" - docs/roadmap-v2.md 0.2. The default
has always been LESSON only; the EA (Schedule 3, S3.3.3) is wider -
programmed teaching, sporting, pastoral care and assembly. Changing the
default silently would change what every load number in this app means,
so the wider definition only takes effect once a school confirms it: a
CONFIRMED industrial_agreement with a load rule that names its
contact_entry_types explicitly. Until then, nothing changes."""

import sqlite3

DEFAULT_CONTACT_ENTRY_TYPES = ("LESSON",)


def resolve_contact_entry_types(conn: sqlite3.Connection) -> tuple[str, ...]:
    """The confirmed agreement's stated contact entry types, preferring a
    SECONDARY load rule (the real school this was built for is Years
    7-12 only - no PRIMARY data exists to prefer instead) - or the
    unchanged LESSON-only default if nothing has been confirmed."""
    row = conn.execute(
        """
        SELECT alr.contact_entry_types
        FROM agreement_load_rule alr
        JOIN industrial_agreement ia ON ia.id = alr.agreement_id
        WHERE ia.confirmed_by IS NOT NULL AND alr.contact_entry_types IS NOT NULL
        ORDER BY CASE alr.sector WHEN 'SECONDARY' THEN 0 ELSE 1 END, ia.confirmed_at DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return DEFAULT_CONTACT_ENTRY_TYPES
    types = tuple(t.strip() for t in row["contact_entry_types"].split(",") if t.strip())
    return types or DEFAULT_CONTACT_ENTRY_TYPES

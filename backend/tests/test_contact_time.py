"""Tests app/analysis/contact_time.py - what counts as EA contact time,
and that it only ever changes once a school confirms an agreement says
so (docs/roadmap-v2.md 0.2). No real EA figures - see tests/synthetic.py."""

from app.analysis.contact_time import DEFAULT_CONTACT_ENTRY_TYPES, resolve_contact_entry_types
from tests.synthetic import build_synthetic_db


def _make_agreement(conn, *, confirmed=True):
    conn.execute(
        "INSERT INTO industrial_agreement (id, name, effective_from, confirmed_by, confirmed_at, created_at) "
        "VALUES (1, 'Test EA', '2023-01-01', ?, ?, 'test')",
        ("hr-rep" if confirmed else None, "2026-01-01T00:00:00" if confirmed else None),
    )


def test_default_is_lesson_only_with_no_agreement():
    conn = build_synthetic_db()
    assert resolve_contact_entry_types(conn) == DEFAULT_CONTACT_ENTRY_TYPES


def test_default_holds_even_with_a_confirmed_agreement_if_no_load_rule_set():
    conn = build_synthetic_db()
    _make_agreement(conn)
    conn.commit()
    assert resolve_contact_entry_types(conn) == DEFAULT_CONTACT_ENTRY_TYPES


def test_unconfirmed_agreement_is_ignored_even_with_a_load_rule():
    conn = build_synthetic_db()
    _make_agreement(conn, confirmed=False)
    conn.execute(
        "INSERT INTO agreement_load_rule (agreement_id, sector, ordinary_hours_per_week, "
        "max_contact_hours_per_week, contact_entry_types) VALUES (1, 'SECONDARY', 30.5, 21.5, 'LESSON,REGISTRATION')"
    )
    conn.commit()
    assert resolve_contact_entry_types(conn) == DEFAULT_CONTACT_ENTRY_TYPES


def test_confirmed_agreement_with_load_rule_widens_the_definition():
    conn = build_synthetic_db()
    _make_agreement(conn)
    conn.execute(
        "INSERT INTO agreement_load_rule (agreement_id, sector, ordinary_hours_per_week, "
        "max_contact_hours_per_week, contact_entry_types) VALUES "
        "(1, 'SECONDARY', 30.5, 21.5, 'LESSON,REGISTRATION,ASSEMBLY,GENERAL_PURPOSE')"
    )
    conn.commit()
    assert resolve_contact_entry_types(conn) == ("LESSON", "REGISTRATION", "ASSEMBLY", "GENERAL_PURPOSE")

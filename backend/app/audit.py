"""Append-only audit trail (PROJECT_ROADMAP.md Milestone 5). One helper,
called from every place an auditable action happens, so the event shape
stays consistent - see docs/privacy-threat-model.md for the full list of
call sites and what's deliberately not logged (no PII, ever)."""

import datetime as dt
import json
import sqlite3


def log_event(
    conn: sqlite3.Connection,
    event_type: str,
    summary: str,
    *,
    actor: str = "local-user",
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: dict | None = None,
) -> None:
    conn.execute(
        "INSERT INTO audit_event (occurred_at, actor, event_type, entity_type, entity_id, summary, detail_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            dt.datetime.now(dt.UTC).isoformat(), actor, event_type,
            entity_type, str(entity_id) if entity_id is not None else None,
            summary, json.dumps(detail) if detail else None,
        ),
    )
    conn.commit()

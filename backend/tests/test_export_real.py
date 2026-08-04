"""End-to-end export gate test against the real export data - the only
way to genuinely exercise the round_trip_reparse gate, which re-ingests
a real, fully-formed .tfx through the application's own production
parser. Skipped automatically when the real export isn't present, same
pattern as the rest of the ingestion test suite. Only asserts on
aggregate/structural outcomes, never prints or asserts on names."""

import json
import sqlite3
from pathlib import Path

import pytest

from app.analysis.run import run_analysis
from app.changes.service import add_proposed_change, approve_change_set, create_change_set, validate_change_set
from app.config import TFX_PATH
from app.export.run import run_export
from app.export.tfx_writer import ExportError, get_approved_change_set
from app.ingest.run import run_full_ingest

pytestmark = pytest.mark.skipif(not TFX_PATH.exists(), reason="real export data not present")


@pytest.fixture(scope="module")
def real_conn(tmp_path_factory) -> sqlite3.Connection:
    db_path = tmp_path_factory.mktemp("export") / "real.sqlite3"
    run_full_ingest(db_path=db_path)
    run_analysis(db_path=db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


def _room_only_fix_change_set(conn: sqlite3.Connection) -> int:
    """Builds a genuinely valid, approved change set against real data:
    moves one half of a real room-double-booking clash to a free room at
    the same slot (the same fix proven to validate cleanly in
    docs/change-sets.md)."""
    finding = conn.execute(
        "SELECT id, evidence_json FROM finding WHERE rule_id = 'room_double_booking' LIMIT 1"
    ).fetchone()
    evidence = json.loads(finding["evidence_json"])
    entry_id = evidence["entries"][1]["entry_id"]
    busy_room_id = conn.execute(
        "SELECT room_id, day_id, period_id FROM timetable_entry WHERE id = ?", (entry_id,)
    ).fetchone()

    busy_rooms_at_slot = {
        r["room_id"] for r in conn.execute(
            "SELECT room_id FROM timetable_entry WHERE day_id = ? AND period_id = ? AND room_id IS NOT NULL",
            (busy_room_id["day_id"], busy_room_id["period_id"]),
        )
    }
    free_room = conn.execute(
        f"SELECT id FROM room WHERE id NOT IN ({','.join('?' for _ in busy_rooms_at_slot)})",
        tuple(busy_rooms_at_slot),
    ).fetchone()

    cs_id = create_change_set(conn, "Real export test", None, "tester")
    add_proposed_change(conn, cs_id, entry_id, after_room_id=free_room["id"], finding_ids=[finding["id"]])
    result = validate_change_set(conn, cs_id)
    assert result["valid"], result
    approve_change_set(conn, cs_id, "tester")
    return cs_id


def test_export_gate_passes_for_a_genuinely_valid_change_set(real_conn):
    cs_id = _room_only_fix_change_set(real_conn)
    result = run_export(real_conn, cs_id, confirm=False)

    assert result["ready"] is True, result["gates"]
    for name, gate in result["gates"].items():
        assert gate["passed"] is True, f"{name} failed: {gate['detail']}"
    assert result["written"] is False  # confirm=False must never write anything


def test_export_blocked_for_unapproved_change_set(real_conn):
    cs_id = create_change_set(real_conn, "Still a draft", None, "tester")
    with pytest.raises(ExportError):
        get_approved_change_set(real_conn, cs_id)
    with pytest.raises(ExportError):
        run_export(real_conn, cs_id, confirm=False)


def test_export_confirm_writes_files_and_they_reparse_cleanly(real_conn, tmp_path, monkeypatch):
    import app.export.run as export_run_module

    monkeypatch.setattr(export_run_module, "OUTPUT_DIR", tmp_path)

    cs_id = _room_only_fix_change_set(real_conn)
    result = run_export(real_conn, cs_id, confirm=True)

    assert result["written"] is True
    assert len(result["output_files"]) == 3
    for f in result["output_files"]:
        assert Path(f).exists()

    tfx_out = next(Path(f) for f in result["output_files"] if f.endswith(".tfx"))
    written = json.loads(tfx_out.read_text(encoding="utf-8"))
    assert len(written["Timetable"]) == 2181  # same count as the real source - nothing added or removed

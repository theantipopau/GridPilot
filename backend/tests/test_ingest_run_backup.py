"""Tests the backup/restore safety net in app.ingest.run.run_full_ingest -
found necessary against real data: a re-ingest that fails partway through
resync_source_tables() (a malformed or genuinely new source file the
parser chokes on) must never leave the working database more broken than
before the attempt started - docs/reingest-persistence.md's whole
premise - but the ingest pipeline commits at several points internally
(start_ingest_run, finish_ingest_run, each parser), so an in-process
transaction/rollback can't be trusted to undo all of it. Only a
whole-file backup, restored on any failure, is a safe guarantee. No real
school data - see tests/synthetic.py."""

import sqlite3

import pytest

import app.ingest.run as ingest_run
from tests.synthetic import build_synthetic_db


def _seed_existing_db(path) -> None:
    conn = build_synthetic_db()
    file_conn = sqlite3.connect(path)
    conn.backup(file_conn)
    file_conn.close()
    conn.close()


def test_a_failed_reingest_restores_the_database_byte_for_byte(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    _seed_existing_db(db_path)
    before = db_path.read_bytes()

    def _boom(conn, ingest_fn):
        raise RuntimeError("simulated mid-ingest crash")

    monkeypatch.setattr(ingest_run, "resync_source_tables", _boom)

    with pytest.raises(RuntimeError, match="simulated mid-ingest crash"):
        ingest_run.run_full_ingest(db_path=db_path)

    assert db_path.read_bytes() == before
    assert not db_path.with_name(db_path.name + ".pre-ingest-backup").exists()


def test_a_successful_reingest_leaves_no_backup_file_behind(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    _seed_existing_db(db_path)

    monkeypatch.setattr(ingest_run, "resync_source_tables", lambda conn, ingest_fn: None)

    ingest_run.run_full_ingest(db_path=db_path)

    assert not db_path.with_name(db_path.name + ".pre-ingest-backup").exists()


def test_a_brand_new_database_is_unaffected_by_the_backup_path(tmp_path, monkeypatch):
    """The backup/restore wrapping only applies to the re-ingest branch -
    a first-ever ingest (fresh_database()) has nothing to back up."""
    db_path = tmp_path / "test.sqlite3"
    assert not db_path.exists()

    called = {"resync": False}
    monkeypatch.setattr(
        ingest_run, "resync_source_tables",
        lambda conn, ingest_fn: called.__setitem__("resync", True),
    )
    monkeypatch.setattr(ingest_run, "_sha256_of", lambda path: "0" * 64)

    # A first ingest calls _do_ingest() directly, never resync_source_tables().
    with pytest.raises(FileNotFoundError):
        # find_sfx_files()/TFX_PATH default to the real (absent-in-CI) export;
        # this fails inside _do_ingest() at ingest_tfx(), which is exactly
        # the point being tested - it must fail there, not in the backup path.
        ingest_run.run_full_ingest(db_path=db_path, tfx_path=tmp_path / "does-not-exist.tfx", sfx_paths=[])

    assert called["resync"] is False
    assert not db_path.with_name(db_path.name + ".pre-ingest-backup").exists()

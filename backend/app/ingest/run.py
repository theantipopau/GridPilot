"""Orchestrates a full ingest into a fresh working SQLite database.
Never reads/writes anything under the source export directory except to
read from it - see app.config for the read-only/working-dir separation."""

import datetime as dt
import hashlib
import shutil
import sqlite3
from pathlib import Path

from app.audit import log_event
from app.config import (
    DB_PATH,
    EMINERVA_SCOURSE_PATH,
    MASTER_TIMETABLE_CYCLE_CSV,
    PERIOD_DETAILS_CSV,
    ROLL_CLASS_DETAILS_CSV,
    ROOM_DETAILS_CSV,
    STUDENT_DETAILS_CSV,
    TEACHER_DETAILS_CSV,
    TFX_PATH,
    find_sfx_files,
)
from app.db.connection import fresh_database, get_connection, init_schema
from app.db.resync import resync_source_tables
from app.ingest.csv_validate import run_all_validations
from app.ingest.eminerva_parser import ingest_eminerva_scourse
from app.ingest.sfx_parser import ingest_all_sfx
from app.ingest.tfx_parser import ingest_tfx


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def start_ingest_run(conn: sqlite3.Connection, tfx_source_path: str) -> int:
    source_hash = _sha256_of(Path(tfx_source_path))
    cur = conn.execute(
        "INSERT INTO ingest_run (started_at, tfx_source_path, tfx_source_sha256) VALUES (?, ?, ?)",
        (dt.datetime.now(dt.UTC).isoformat(), tfx_source_path, source_hash),
    )
    conn.commit()
    return cur.lastrowid


def finish_ingest_run(conn: sqlite3.Connection, ingest_run_id: int) -> None:
    conn.execute(
        "UPDATE ingest_run SET finished_at = ? WHERE id = ?",
        (dt.datetime.now(dt.UTC).isoformat(), ingest_run_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT tfx_source_path, tfx_source_sha256 FROM ingest_run WHERE id = ?", (ingest_run_id,)
    ).fetchone()
    log_event(
        conn, "ingest_completed", f"Ingest run {ingest_run_id} completed",
        entity_type="ingest_run", entity_id=ingest_run_id,
        detail={"source_path": row[0], "source_sha256": row[1]},
    )


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = [
        "day", "period", "year_level", "room", "faculty", "teacher", "teacher_faculty",
        "roll_class", "student", "subject", "class_name", "class_group", "class_group_course",
        "class_group_course_room_override", "timetable_entry", "enrolment", "yard_duty_area",
        "yard_duty_session", "yard_duty_allocation", "ingest_discrepancy",
        "school_setting", "blocking_line", "blocking_line_class_group",
        "room_pool", "room_pool_room", "room_pool_class_name",
        "sfx_file", "sfx_line", "sfx_subject", "sfx_option", "sfx_class", "sfx_student_preference",
    ]
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


def run_full_ingest(tfx_path=None, db_path=None, sfx_paths=None, validate_against_csvs=True) -> dict[str, int]:
    """Fresh-loads the working DB from the .tfx export (primary source),
    cross-validates against the CSV exports, layers in the eMinerva
    enrolment list, then ingests every Student Options (.sfx) file found
    (or the explicit list given). Returns aggregate table counts only -
    never prints or returns row-level PII.

    tfx_path defaults to the newest .tfx under SOURCE_DIR (see
    app.config.default_tfx_path) - safe to leave unset when a new term's
    export replaces the one this was built against; sfx_paths defaults to
    every .sfx found the same way, so adding/removing a year level's file
    needs no code change either.

    If the target database doesn't exist yet, it's created fresh (nothing
    to preserve). If it already exists, this re-ingests through
    app.db.resync.resync_source_tables() instead of wiping the file, so
    composite-group reviews, change sets, and the audit trail survive a
    re-ingest - see docs/reingest-persistence.md."""
    path = tfx_path or TFX_PATH
    sfx_files = sfx_paths if sfx_paths is not None else find_sfx_files()
    target_db_path = Path(db_path) if db_path is not None else DB_PATH

    def _do_ingest() -> None:
        run_id = start_ingest_run(conn, str(path))
        ingest_tfx(conn, path, run_id)
        # CSV/eMinerva cross-validation reads from a *fixed* path under
        # SOURCE_DIR, independent of whatever .tfx was actually ingested -
        # correct for the CLI workflow, where a term's .tfx and its CSV/
        # eMinerva exports are dropped into Timetabler Export/ together,
        # but wrong for a browser-uploaded .tfx describing a different
        # cohort entirely (e.g. next year's construction file cross-
        # checked against this year's leftover CSVs - guaranteed to
        # "fail loudly" over mismatches that were never real problems).
        # validate_against_csvs=False (the browser upload path, see
        # app/api/ingest.py) honours this module's own documented
        # contract: "a .tfx uploaded on its own is a complete, valid
        # ingest" without them.
        if validate_against_csvs:
            run_all_validations(conn, run_id, {
                "rooms": ROOM_DETAILS_CSV,
                "periods": PERIOD_DETAILS_CSV,
                "teachers": TEACHER_DETAILS_CSV,
                "roll_classes": ROLL_CLASS_DETAILS_CSV,
                "students": STUDENT_DETAILS_CSV,
                "master_timetable": MASTER_TIMETABLE_CYCLE_CSV,
            })
            ingest_eminerva_scourse(conn, run_id, EMINERVA_SCOURSE_PATH)
        ingest_all_sfx(conn, sfx_files, run_id)
        finish_ingest_run(conn, run_id)

    is_first_ingest = not target_db_path.exists()
    if is_first_ingest:
        conn = fresh_database(target_db_path)
        try:
            _do_ingest()
            return table_counts(conn)
        finally:
            conn.close()

    # A re-ingest's resync_source_tables() deletes every source-derived
    # table in one committed step before repopulating them from the new
    # file (see app/db/resync.py) - a crash partway through repopulation
    # (a malformed source file, a parser bug on data this app has never
    # seen before) would otherwise leave the working database with those
    # tables permanently empty and every human review decision gone, with
    # no way back. Found the hard way: ingesting a genuinely new, still-
    # under-construction .tfx failed on a duplicate class_name.code deep
    # in the parser, after the old data was already wiped.
    #
    # A whole-file backup, restored on any failure, is the simplest
    # correct guarantee here - the ingest pipeline commits at several
    # points internally (start_ingest_run, finish_ingest_run, each
    # parser), so a single in-process transaction/rollback can't be
    # trusted to undo all of it; only the file itself is a safe unit.
    backup_path = target_db_path.with_name(target_db_path.name + ".pre-ingest-backup")
    shutil.copy2(target_db_path, backup_path)
    conn = get_connection(target_db_path)
    init_schema(conn)  # idempotent (CREATE TABLE IF NOT EXISTS) - picks up any schema additions
    try:
        resync_source_tables(conn, _do_ingest)
        result = table_counts(conn)
    except Exception:
        conn.close()
        shutil.copy2(backup_path, target_db_path)
        raise
    else:
        conn.close()
        return result
    finally:
        backup_path.unlink(missing_ok=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest a Timetabling Solutions export into the working database.")
    parser.add_argument("--tfx", type=Path, default=None,
                         help="Path to a specific .tfx file. Defaults to the newest .tfx under the source folder.")
    args = parser.parse_args()

    print(f"Ingesting: {args.tfx or TFX_PATH}")
    counts = run_full_ingest(tfx_path=args.tfx)
    for name, n in counts.items():
        print(f"{name}: {n}")

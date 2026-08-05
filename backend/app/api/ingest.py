"""Load a .tfx (and optional .sfx) file straight from the browser, rather
than requiring it be dropped into Timetabler Export/ first - makes the
"load a .tfx, see it, change it, export it" loop reachable from the UI,
not just the CLI ingest step (app/ingest/run.py).

Uploaded files are saved under DATA_DIR/uploads, never into SOURCE_DIR -
the read-only/working-dir separation documented in app/config.py holds
here too. Ingestion itself is unchanged: a .tfx uploaded on its own is a
complete, valid ingest (CSV/eMinerva cross-validation is supplementary
and skips gracefully when those files aren't present - see
app/ingest/csv_validate.py and app/ingest/eminerva_parser.py)."""

import datetime as dt
import re
import sqlite3
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.analysis.run import run_analysis
from app.config import DATA_DIR, DB_PATH, ensure_dirs
from app.ingest.errors import IngestError
from app.ingest.run import run_full_ingest

router = APIRouter()

UPLOAD_DIR = DATA_DIR / "uploads"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # real exports are a few MB; generous headroom


@router.get("/ingest/status")
def ingest_status() -> dict:
    # sqlite3.connect() silently creates an empty file at DB_PATH if none
    # exists yet - checking DB_PATH.exists() alone would report "has data"
    # incorrectly (or crash on the next query) the moment any other
    # request has already opened one. Check the schema itself instead -
    # see app/api/deps.py's _require_schema_initialized for the same
    # reasoning applied to every other endpoint.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'timetable_entry'"
        ).fetchone()
        if table_exists is None:
            return {"has_data": False, "last_ingest": None}

        has_data = conn.execute("SELECT COUNT(*) FROM timetable_entry").fetchone()[0] > 0
        last_run = conn.execute(
            "SELECT started_at, finished_at, tfx_source_path, source_file_id FROM ingest_run "
            "WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return {
            "has_data": has_data,
            "last_ingest": dict(last_run) if last_run else None,
        }
    finally:
        conn.close()


def _safe_filename(name: str) -> str:
    # A browser only ever sends a bare filename, but never trust it as a
    # path component without stripping directory parts and anything that
    # isn't a plain filename character first.
    base = Path(name).name
    return re.sub(r"[^A-Za-z0-9 ._-]", "_", base) or "upload"


async def _save_upload(upload: UploadFile, suffix: str) -> Path:
    if not upload.filename or not upload.filename.lower().endswith(suffix):
        raise HTTPException(status_code=400, detail=f"{upload.filename or '(unnamed file)'} is not a {suffix} file")

    ensure_dirs()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S%f")
    dest = UPLOAD_DIR / f"{stamp}_{_safe_filename(upload.filename)}"

    size = 0
    with open(dest, "wb") as f:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413, detail=f"{upload.filename} is larger than the {MAX_UPLOAD_BYTES // (1024*1024)}MB limit"
                )
            f.write(chunk)
    return dest


@router.post("/ingest/upload")
async def upload_and_ingest(
    tfx_file: UploadFile = File(...),
    sfx_files: list[UploadFile] = File(default=[]),
) -> dict:
    tfx_path = await _save_upload(tfx_file, ".tfx")
    sfx_paths = [await _save_upload(f, ".sfx") for f in sfx_files if f.filename]

    try:
        counts = await run_in_threadpool(run_full_ingest, tfx_path=tfx_path, sfx_paths=sfx_paths)
    except IngestError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    analysis = await run_in_threadpool(run_analysis)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        discrepancies = [
            dict(r) for r in conn.execute(
                "SELECT check_name, severity, description FROM ingest_discrepancy "
                "WHERE ingest_run_id = (SELECT MAX(id) FROM ingest_run) "
                "ORDER BY CASE severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END"
            )
        ]
    finally:
        conn.close()

    return {
        "counts": counts,
        "analysis": analysis,
        "discrepancies": discrepancies,
        "tfx_filename": tfx_file.filename,
        "sfx_filenames": [f.filename for f in sfx_files if f.filename],
    }

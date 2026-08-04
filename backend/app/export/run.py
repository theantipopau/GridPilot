"""CLI entry point for the export gate (PROJECT_ROADMAP.md Milestone 6).
Deliberately CLI-only, like app/retention.py, and for the same reason:
producing a file that could end up back in Timetabling Solutions is a
consequential action that should require someone at a terminal choosing
to run it, not one click away in a UI. The UI can preview validation
results (GET /api/change-sets/{id}/export-preview - read-only, writes
nothing) but only this script actually produces a file, and only with
--confirm.

"Backup" (PROJECT_ROADMAP.md: "backup and timestamped output filename"):
every export produces a uniquely timestamped file and never overwrites
an existing one, so the output/ directory is itself a complete history
of every export ever generated - there's no separate backup step because
nothing is ever replaced in place.

Usage:
    python -m app.export.run --change-set-id 5              # dry run: validate, print gate results
    python -m app.export.run --change-set-id 5 --confirm     # write files if every gate passes
"""

import argparse
import datetime as dt
import json
import re
import sqlite3

from app.audit import log_event
from app.config import DB_PATH, OUTPUT_DIR, TFX_PATH
from app.export.tfx_writer import (
    ExportError,
    apply_change_set,
    build_reverse_lookups,
    get_approved_change_set,
    get_changes_with_source_ref,
    load_source_json,
)
from app.export.validate import ValidationReport, validate_export


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return slug or "change-set"


def run_export(conn: sqlite3.Connection, change_set_id: int, confirm: bool = False) -> dict:
    change_set = get_approved_change_set(conn, change_set_id)
    changes = get_changes_with_source_ref(conn, change_set_id)
    if not changes:
        raise ExportError(f"Change set {change_set_id} has no proposed changes.")

    original = load_source_json(TFX_PATH)
    lookups = build_reverse_lookups(conn)
    patched, changelog = apply_change_set(original, changes, lookups)

    report = validate_export(conn, change_set_id, original, patched, changes, changelog)

    result = {
        "change_set_id": change_set_id,
        "change_set_name": change_set["name"],
        "ready": report.ready,
        "gates": {name: {"passed": g.passed, "detail": g.detail} for name, g in report.gates.items()},
        "changelog": report.changelog,
        "written": False,
        "output_files": [],
    }

    if not report.ready:
        return result

    if not confirm:
        return result

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    base_name = f"{_slug(change_set['name'])}_{change_set_id}_{timestamp}"

    tfx_path = OUTPUT_DIR / f"{base_name}.tfx"
    changelog_path = OUTPUT_DIR / f"{base_name}_changelog.json"
    validation_path = OUTPUT_DIR / f"{base_name}_validation.json"

    for p in (tfx_path, changelog_path, validation_path):
        if p.exists():
            raise ExportError(f"Refusing to overwrite existing file {p}")

    tfx_path.write_text(json.dumps(patched, indent=2), encoding="utf-8")
    changelog_path.write_text(json.dumps(report.changelog, indent=2), encoding="utf-8")
    validation_path.write_text(json.dumps(result["gates"], indent=2), encoding="utf-8")

    log_event(
        conn, "export_generated", f"Exported change set {change_set_id} to {tfx_path.name}",
        entity_type="change_set", entity_id=change_set_id,
        detail={"output_file": str(tfx_path), "change_count": len(changelog)},
    )

    result["written"] = True
    result["output_files"] = [str(tfx_path), str(changelog_path), str(validation_path)]
    return result


def _main() -> None:
    parser = argparse.ArgumentParser(description="Export an approved change set to a re-importable .tfx file.")
    parser.add_argument("--change-set-id", type=int, required=True)
    parser.add_argument("--confirm", action="store_true", help="Actually write files (default is a dry run).")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        result = run_export(conn, args.change_set_id, confirm=args.confirm)
    except ExportError as e:
        print(f"Export blocked: {e}")
        raise SystemExit(1) from e
    finally:
        conn.close()

    print(f"Change set {result['change_set_id']} ({result['change_set_name']!r}): ready={result['ready']}")
    for name, gate in result["gates"].items():
        status = "PASS" if gate["passed"] else "FAIL"
        print(f"  [{status}] {name}")
        if not gate["passed"]:
            print(f"         {gate['detail']}")

    if not result["ready"]:
        print("\nNot ready - fix the failing gate(s) above before exporting.")
        raise SystemExit(1)

    if result["written"]:
        print("\nWritten:")
        for f in result["output_files"]:
            print(f"  {f}")
    else:
        print(f"\nDry run - {len(result['changelog'])} change(s) would be written. Re-run with --confirm to write.")


if __name__ == "__main__":
    _main()

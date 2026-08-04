"""Explicit data-retention/purge action (PROJECT_ROADMAP.md Milestone 5).
Deletes the working database and generated output files - never anything
under SOURCE_DIR (see app.config's read-only/working-dir separation).

Deliberately CLI-only, not exposed over the API: this is a destructive
action a person should run deliberately at a terminal, not something one
click in the UI could trigger. Defaults to a dry run - nothing is deleted
until --confirm is passed.

Note on the audit trail: since this purges the working database itself,
it necessarily also removes that database's own audit_event history - a
purge is an intentional clean slate, not a selectively-forgetful edit.
Back up data/sophia_tt.sqlite3 first if you need to keep the record."""

import argparse
from pathlib import Path

from app.config import DATA_DIR, OUTPUT_DIR


def find_purgeable_files() -> list[Path]:
    targets = []
    if DATA_DIR.exists():
        targets.extend(sorted(p for p in DATA_DIR.rglob("*") if p.is_file()))
    if OUTPUT_DIR.exists():
        targets.extend(sorted(p for p in OUTPUT_DIR.rglob("*") if p.is_file()))
    return targets


def purge(confirm: bool = False) -> dict:
    files = find_purgeable_files()
    if not confirm:
        return {"dry_run": True, "would_delete": [str(p) for p in files], "deleted": []}

    deleted = []
    for p in files:
        p.unlink()
        deleted.append(str(p))
    return {"dry_run": False, "would_delete": [], "deleted": deleted}


def _main() -> None:
    parser = argparse.ArgumentParser(description="Purge the working database and generated outputs.")
    parser.add_argument("--confirm", action="store_true", help="Actually delete (default is a dry run).")
    args = parser.parse_args()

    result = purge(confirm=args.confirm)
    if result["dry_run"]:
        print("Dry run - nothing deleted. Files that would be removed:")
        for f in result["would_delete"]:
            print(f"  {f}")
        print(f"\n{len(result['would_delete'])} file(s). Re-run with --confirm to actually delete.")
    else:
        print(f"Deleted {len(result['deleted'])} file(s):")
        for f in result["deleted"]:
            print(f"  {f}")


if __name__ == "__main__":
    _main()
